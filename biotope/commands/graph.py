"""Independent graph workspace operations with human and structured output."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import click

from biotope.commands._graph_output import GraphOutput
from biotope.graph.artifacts import check_report_destination, save_report
from biotope.graph.check import check_pipeline
from biotope.graph.reports import CheckFailed, Finding
from biotope.graph.workspace import select_workspace


@click.group(name="graph")
def graph_group() -> None:
    """Scaffold, check, assess, visualize or build one graph workspace."""


def workspace_options(function: Callable[..., Any]) -> Callable[..., Any]:
    function = click.option("--json", "as_json", is_flag=True, help="Emit one structured report to stdout.")(function)
    return click.option(
        "--graph",
        "graph_path",
        default="graph",
        type=click.Path(path_type=Path),
        help="Graph workspace; defaults to graph/ in the current directory.",
    )(function)


def command_report(
    operation: str, graph_path: Path, as_json: bool, action: Callable[[GraphOutput, Path], dict[str, Any]]
) -> None:
    root = graph_path.absolute()
    output = GraphOutput(operation, str(graph_path), as_json)
    report: dict[str, Any]
    with output:
        try:
            report = action(output, root)
        except CheckFailed as exc:
            report = exc.report
        except Exception as exc:
            report = getattr(exc, "report", None) or {
                "schema_version": 1,
                "report_kind": "biotope." + operation,
                "operation": operation,
                "state": "failed",
                "findings": [
                    Finding(
                        "workspace.load" if operation == "check" else operation + ".failed",
                        "error",
                        str(graph_path),
                        str(exc),
                    ).to_json()
                ],
            }
    if operation in ("quality", "build") and report.get("state") == "failed":
        report.setdefault("quality", {"state": "not_run", "reason": "Operation could not start"})
    report.setdefault("operation", operation)
    report["graph"] = str(root)
    output.finish(report)
    if report.get("state") == "failed":
        raise click.exceptions.Exit(1)


def save_load_failure(operation: str, root: Path, path: Path, error: Exception) -> dict[str, Any]:
    """Record an unavailable pipeline without claiming definitions or data were checked."""
    report = {
        "schema_version": 1,
        "report_kind": "biotope." + operation,
        "operation": operation,
        "graph": str(root),
        "state": "failed",
        "scope": None,
        "definitions": None,
        "outputs": [],
        "finished": datetime.now(timezone.utc).isoformat(),
        "error": str(error),
        "quality": {"state": "not_run", "reason": "Workspace could not be loaded"},
        "report_path": str(path),
        "findings": [Finding("workspace.load", "error", str(root), str(error)).to_json()],
    }
    save_report(path, json.dumps(report, indent=2) + "\n", "biotope." + operation)
    return report


@graph_group.command()
@workspace_options
def scaffold(graph_path: Path, as_json: bool) -> None:
    """Create graph boilerplate without scanning data or executing a pipeline."""

    def action(output: GraphOutput, target: Path) -> dict[str, Any]:
        if target.exists() or target.is_symlink():
            raise ValueError(f"{target} already exists; reuse its authored files. Nothing was changed.")
        template = Path(__file__).resolve().parents[1] / "templates/graph"
        shutil.copytree(template, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        return {
            "schema_version": 1,
            "report_kind": "biotope.scaffold",
            "operation": "scaffold",
            "state": "complete",
            "path": str(target),
            "files": sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()),
        }

    command_report("scaffold", graph_path, as_json, action)


@graph_group.command()
@workspace_options
def check(graph_path: Path, as_json: bool) -> None:
    """Check definitions and Python types without invoking loaders or mappings."""

    def action(output: GraphOutput, root: Path) -> dict[str, Any]:
        with select_workspace(root) as workspace:
            return check_pipeline(workspace.pipeline(), phase=output.phase, on_finding=output.on_finding)

    command_report("check", graph_path, as_json, action)


@graph_group.command()
@workspace_options
@click.option(
    "--out", required=True, type=click.Path(path_type=Path), help="New output directory; never overwrite a run."
)
def build(graph_path: Path, as_json: bool, out: Path) -> None:
    """Run loaders, mappings and quality checks, then export through BioCypher."""
    from biotope.graph.build import run_pipeline

    destination = out.absolute()

    def action(output: GraphOutput, root: Path) -> dict[str, Any]:
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"Output directory already exists: {destination}")
        try:
            with select_workspace(root) as workspace:
                pipeline = workspace.pipeline()
                return run_pipeline(pipeline, destination, phase=output.phase, on_finding=output.on_finding)
        except Exception as exc:
            if hasattr(exc, "report") or destination.exists() or not root.is_dir():
                raise
            destination.mkdir(parents=True, exist_ok=False)
            return save_load_failure("build", root, destination / "run.json", exc)

    command_report("build", graph_path, as_json, action)


@graph_group.command()
@workspace_options
def quality(graph_path: Path, as_json: bool) -> None:
    """Run project loaders and mappings; assess Python graph objects without export."""
    from biotope.graph.build import assess_pipeline

    def action(output: GraphOutput, root: Path) -> dict[str, Any]:
        path = root / "reports/quality.json"
        # Check before any project code runs; preserve an unrelated authored report.
        check_report_destination(path, "biotope.quality")
        try:
            with select_workspace(root) as workspace:
                pipeline = workspace.pipeline()
                return assess_pipeline(pipeline, path, phase=output.phase, on_finding=output.on_finding)
        except Exception as exc:
            if hasattr(exc, "report"):
                raise
            if root.is_dir():
                return save_load_failure("quality", root, path, exc)
            raise

    command_report("quality", graph_path, as_json, action)


@graph_group.command()
@workspace_options
@click.option(
    "--report", "report_path", type=click.Path(path_type=Path), help="Optional quality.json or run.json observations."
)
@click.option(
    "--out", type=click.Path(path_type=Path), help="HTML destination; defaults to <graph>/reports/metagraph.html."
)
def metagraph(graph_path: Path, as_json: bool, report_path: Path | None, out: Path | None) -> None:
    """Inspect declared topology; optionally overlay a matching saved assessment."""
    from biotope.graph.metagraph import describe_metagraph, render_metagraph

    if as_json and out is not None:
        raise click.UsageError("--json and --out are mutually exclusive")
    report_path = report_path.absolute() if report_path is not None else None
    destination = out.absolute() if out is not None else graph_path.absolute() / "reports/metagraph.html"

    def action(output: GraphOutput, root: Path) -> dict[str, Any]:
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path else None
        with select_workspace(root) as workspace:
            document = describe_metagraph(workspace.topology(), report)
        if not as_json:
            save_report(destination, render_metagraph(document), "html")
            document["html_path"] = str(destination)
        return document

    command_report("metagraph", graph_path, as_json, action)
