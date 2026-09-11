"""Run records and the explicit project pipeline entry point."""

from __future__ import annotations

import importlib.metadata
import json
import platform
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from biotope.graph.artifacts import check_report_destination, save_report
from biotope.graph.check import check_pipeline
from biotope.graph.context import build_query_context
from biotope.graph.contracts import Pipeline
from biotope.graph.output import BioCypherWriter, GraphWriter, export_labels
from biotope.graph.quality import analyze_quality
from biotope.graph.reports import CheckFailed, Finding, FindingSink, Phase
from biotope.graph.runtime import RunContext
from biotope.graph.sources import digest
from biotope.graph.validation import run_validation


class RunFailed(ValueError):
    """Carry the failed run report to an API or CLI caller."""

    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(report["error"])


def run_pipeline(
    pipeline: Pipeline,
    output: Path,
    *,
    writer: GraphWriter | None = None,
    phase: Phase | None = None,
    on_finding: FindingSink | None = None,
) -> dict[str, Any]:
    """Execute and assess once, then export into a new run directory."""
    output.mkdir(parents=True, exist_ok=False)
    return _execute(pipeline, output / "run.json", output=output, writer=writer, phase=phase, on_finding=on_finding)


def assess_pipeline(
    pipeline: Pipeline, report_path: Path, *, phase: Phase | None = None, on_finding: FindingSink | None = None
) -> dict[str, Any]:
    """Execute and assess once without constructing an exporter."""
    check_report_destination(report_path, "biotope.quality")
    return _execute(pipeline, report_path, phase=phase, on_finding=on_finding)


def _execute(
    pipeline: Pipeline,
    report_path: Path,
    *,
    output: Path | None = None,
    writer: GraphWriter | None = None,
    phase: Phase | None = None,
    on_finding: FindingSink | None = None,
) -> dict[str, Any]:
    operation = "quality" if output is None else "build"
    report: dict[str, Any] = {
        "schema_version": 1,
        "report_kind": "biotope." + operation,
        "operation": operation,
        "pipeline": pipeline.name,
        "state": "running",
        "started": datetime.now(timezone.utc).isoformat(),
        "scope": pipeline.scope,
        "settings": pipeline.settings,
        "policies": pipeline.policies,
        "variability": pipeline.variability,
        "python": platform.python_version(),
        "outputs": [],
        "report_path": str(report_path),
        "findings": [],
        "audits": [],
        "validation": {"state": "not_run", "reason": "Pipeline execution and integrity checks have not completed"},
        "quality": {"state": "not_run", "reason": "Pipeline execution and integrity checks have not completed"},
        "dependencies": {
            name: _software(name) for name in ("biotope", "croissant-baker", "pyright", *pipeline.dependencies)
        },
    }
    context: RunContext | None = None
    exporter = (writer or BioCypherWriter()) if output is not None else None

    def save() -> None:
        save_report(
            report_path, json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", "biotope." + operation
        )

    def collect() -> None:
        """Refresh the run's own evidence; idempotent so the context can be generated from it."""
        if context is None:
            return
        report["audits"] = [asdict(item) for item in context.audits]
        report["loaded_records"] = context.loaded
        report["graph_objects"] = {"nodes": len(context.nodes), "edges": len(context.edges)}
        report["source_versions"] = sorted(context.source_versions)
        kept: list[Any] = [item for item in report["findings"] if item.get("kind") != "exclusion"]
        report["findings"] = [*kept, *context.findings]

    save()
    stage = "definitions"
    try:
        report["definitions"] = check_pipeline(pipeline, phase=phase, on_finding=on_finding)
        if exporter is not None:
            stage = "environment"
            if phase:
                phase("Checking the exporter")
            report["exporter"] = exporter.check_environment()
        stage = "execution"
        context = RunContext(pipeline)
        if phase:
            phase("Running project loaders and mappings")
        pipeline.run(context)
        if phase:
            phase("Checking references")
        stage = "integrity"
        context.validate_references()
        stage = "validation"
        collect()
        sealed = context.content_digest() if pipeline.validation_checks else None
        report["validation"] = run_validation(
            pipeline, context.view(), context.snapshot(), phase=phase, on_finding=on_finding
        )
        if sealed is not None and context.content_digest() != sealed:
            raise ValueError(
                "A validation check modified the graph. Checks inspect the built graph and must "
                "not change it; the run is abandoned rather than exporting an unchecked graph."
            )
        stage = "quality"
        report["quality"] = analyze_quality(context.stores(), phase=phase, on_finding=on_finding).to_json()
        if report["validation"]["state"] == "failed":
            stage = "validation"
            raise ValueError(
                "Declared validation failed: "
                + "; ".join(
                    f"{item['name']}: {item['detail']}"
                    for item in report["validation"]["checks"]
                    if item["state"] == "failed"
                )
            )
        report["query_context"] = build_query_context(
            pipeline,
            schema=context.schema,
            descriptions=pipeline.topology.descriptions(),
            labels=export_labels(context.schema),
            report=report,
        )
        if exporter is not None and output is not None:
            stage = "export"
            if phase:
                phase("Exporting BioCypher files")
            report["dependencies"]["biocypher"] = _software("biocypher")
            report["outputs"] = exporter.write(context, output, query_context=report["query_context"])
            report["graph_digest"] = context.content_digest()
        report["state"] = "complete"
    except Exception as exc:
        if isinstance(exc, CheckFailed):
            report["definitions"] = exc.report
        else:
            report["findings"].append(Finding(stage + ".failed", "error", pipeline.name, str(exc)).to_json())
        for section in ("validation", "quality"):
            if report[section]["state"] == "not_run":
                report[section].update(blocked_by=stage + ".failed", reason=f"{stage.capitalize()} failed: {exc}")
        report.update(state="failed", error=str(exc))
        raise RunFailed(report) from exc
    finally:
        report["finished"] = datetime.now(timezone.utc).isoformat()
        collect()
        save()
    return report


def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def _software(package: str) -> dict[str, object]:
    """Record installed version and available development-install identity."""
    info: dict[str, object] = {"version": _version(package)}
    try:
        direct_url = importlib.metadata.distribution(package).read_text("direct_url.json")
        if direct_url:
            origin = json.loads(direct_url)
            info["editable"] = origin.get("dir_info", {}).get("editable", False)
            if "vcs_info" in origin:
                info["vcs"] = origin["vcs_info"]
    except (importlib.metadata.PackageNotFoundError, ValueError):
        info["install_provenance"] = "unavailable"
    if package == "biotope":
        # Include uncommitted editable code too; HEAD/version alone cannot identify it.
        root = Path(__file__).resolve().parents[1]
        info["source_digest"] = digest(
            {
                str(path.relative_to(root)): digest(path.read_text(encoding="utf-8"))
                for path in sorted(root.rglob("*.py"))
            }
        )
    return info
