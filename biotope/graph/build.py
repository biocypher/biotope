"""Run records and the explicit project pipeline entry point."""

from __future__ import annotations

import importlib.metadata
import json
import platform
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from biotope.graph.check import check_pipeline
from biotope.graph.contracts import Pipeline
from biotope.graph.output import BioCypherWriter, GraphWriter
from biotope.graph.runtime import RunContext
from biotope.graph.sources import digest, write_text_atomic
from biotope.graph.topology import concept_id


def run_pipeline(pipeline: Pipeline, output: Path, *, writer: GraphWriter | None = None) -> dict[str, object]:
    """Check, explicitly execute, and export into a new directory.

    Failure leaves an honest failed run record; existing runs are never replaced.
    Payload versions come from project evidence, not a new full-data hash pass.
    """
    output.mkdir(parents=True, exist_ok=False)
    report: dict[str, object] = {
        "pipeline": pipeline.name,
        "state": "running",
        "started": datetime.now(timezone.utc).isoformat(),
        "scope": pipeline.scope,
        "settings": pipeline.settings,
        "policies": pipeline.policies,
        "variability": pipeline.variability,
        "python": platform.python_version(),
        "dependencies": {
            name: _software(name)
            for name in ("biotope", "croissant-baker", "biocypher", "pyright", *pipeline.dependencies)
        },
    }
    context: RunContext | None = None

    def save() -> None:
        write_text_atomic(output / "run.json", json.dumps(report, indent=2, sort_keys=True) + "\n")

    save()
    try:
        report["definitions"] = check_pipeline(pipeline)
        context = RunContext(pipeline)
        pipeline.run(context)
        context.validate_references()
        report["outputs"] = (writer or BioCypherWriter()).write(context, output)
        content = [
            [kind, identity, concept_id(type(row.value)), _payload(row.value)]
            for kind, records in (("node", context.nodes), ("edge", context.edges))
            for identity, row in sorted(records.items())
        ]
        report["graph_digest"] = digest(content)
        report["state"] = "complete"
    except Exception as exc:
        report["state"] = "failed"
        report["error"] = str(exc)
        raise
    finally:
        report["finished"] = datetime.now(timezone.utc).isoformat()
        if context is not None:
            report["loaded_records"] = context.loaded
            report["graph_objects"] = {"nodes": len(context.nodes), "edges": len(context.edges)}
            report["findings"] = context.findings
            report["source_versions"] = sorted(context.source_versions)
        save()
    return report


def _payload(value: object) -> dict[str, object]:
    if not is_dataclass(value) or isinstance(value, type):
        raise ValueError("Graph outputs must be dataclass instances")
    return asdict(value)


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
