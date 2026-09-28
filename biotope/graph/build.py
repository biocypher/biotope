"""Run records and the explicit project pipeline entry point."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from biotope.graph.artifacts import RUN_REPORT, check_build_destination, record_failed_build, report_text, save_report
from biotope.graph.check import check_pipeline
from biotope.graph.contracts import Pipeline
from biotope.graph.output import BioCypherWriter, GraphWriter
from biotope.graph.quality import analyze_quality
from biotope.graph.reports import REPORT_SCHEMA_VERSION, CheckFailed, Finding, FindingSink, Phase
from biotope.graph.runtime import RunContext
from biotope.graph.sources import digest
from biotope.graph.workspace import Workspace


class RunFailed(ValueError):
    """Carry the failed run report to an API or CLI caller."""

    def __init__(self, report: dict[str, Any]):
        self.report = report
        super().__init__(report["error"])


def run_pipeline(
    pipeline: Pipeline,
    output: Path,
    *,
    workspace: Workspace | None = None,
    writer: GraphWriter | None = None,
    phase: Phase | None = None,
    on_finding: FindingSink | None = None,
) -> dict[str, Any]:
    """Build in staging, then replace the previous generated build on success."""
    output = output.absolute()
    check_build_destination(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    backup = staging.with_name(staging.name + "-previous")
    try:
        try:
            report = _execute(pipeline, staging, workspace=workspace, writer=writer, phase=phase, on_finding=on_finding)
        except RunFailed as exc:
            record_failed_build(output, exc.report)
            raise
        report["report_path"] = str(output / RUN_REPORT)
        save_report(staging / RUN_REPORT, report_text(report), "biotope.build")
        check_build_destination(output)
        if output.exists():
            output.replace(backup)
        try:
            staging.replace(output)
        except OSError:
            if backup.exists():
                backup.replace(output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        return report
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def assess_pipeline(
    pipeline: Pipeline,
    *,
    workspace: Workspace | None = None,
    phase: Phase | None = None,
    on_finding: FindingSink | None = None,
) -> dict[str, Any]:
    """Execute and assess once without constructing an exporter or writing a report."""
    return _execute(pipeline, None, workspace=workspace, phase=phase, on_finding=on_finding)


def _execute(
    pipeline: Pipeline,
    output: Path | None,
    *,
    workspace: Workspace | None = None,
    writer: GraphWriter | None = None,
    phase: Phase | None = None,
    on_finding: FindingSink | None = None,
) -> dict[str, Any]:
    operation = "quality" if output is None else "build"
    report_path = output / RUN_REPORT if output is not None else None
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
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
        "report_path": str(report_path) if report_path is not None else None,
        "findings": [],
        "audits": [],
        "quality": {"state": "not_run", "reason": "Pipeline execution and integrity checks have not completed"},
        "dependencies": {
            name: _software(name) for name in ("biotope", "croissant-baker", "pyright", *pipeline.dependencies)
        },
    }
    context: RunContext | None = None
    exporter = (writer or BioCypherWriter()) if output is not None else None

    def save() -> None:
        if report_path is not None:
            save_report(report_path, report_text(report), "biotope." + operation)

    def collect() -> None:
        """Refresh the run's own evidence; idempotent, so a failure report keeps what was measured."""
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
        report["definitions"] = check_pipeline(pipeline, workspace=workspace, phase=phase, on_finding=on_finding)
        for providers in report["definitions"].get("imports", {}).values():
            for name in providers:
                if name not in report["dependencies"]:
                    report["dependencies"][name] = _software(name)
        if exporter is not None:
            stage = "environment"
            if phase:
                phase("Checking the exporter")
            report["exporter"] = exporter.check_environment()
        stage = "execution"
        context = RunContext(pipeline, exporter.check_object if exporter is not None else None)
        if phase:
            phase("Running project loaders and mappings")
        pipeline.run(context)
        unfinished = {source.name for source in pipeline.sources} - context.completed_sources
        if unfinished:
            raise ValueError(f"Selected source loaders did not finish: {sorted(unfinished)}")
        if phase:
            phase("Checking references")
        stage = "integrity"
        context.validate_references()
        collect()
        stage = "quality"
        report["quality"] = analyze_quality(context.stores(), phase=phase, on_finding=on_finding).to_json()
        if exporter is not None and output is not None:
            stage = "export"
            if phase:
                phase("Exporting BioCypher files")
            report["dependencies"]["biocypher"] = _software("biocypher")
            report["outputs"] = exporter.write(context, output)
            report["graph_digest"] = context.content_digest()
        report["state"] = "complete"
    except Exception as exc:
        if isinstance(exc, CheckFailed):
            report["definitions"] = exc.report
        else:
            report["findings"].append(Finding(stage + ".failed", "error", pipeline.name, str(exc)).to_json())
        if report["quality"]["state"] == "not_run":
            report["quality"].update(blocked_by=stage + ".failed", reason=f"{stage.capitalize()} failed: {exc}")
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
