"""Definition checking and explicitly requested graph construction."""

import importlib
import json
import shutil
import sys
from pathlib import Path

import click

from biotope.graph.contracts import Pipeline


@click.group(name="graph")
def graph_group() -> None:
    """Scaffold graph Python, check definitions, or explicitly run a pipeline."""


@graph_group.command()
@click.option("--json", "as_json", is_flag=True, help="Emit the workspace path and created files as JSON.")
def scaffold(as_json: bool) -> None:
    """Create graph/ in the current directory, without scanning data or building."""
    target = Path.cwd() / "graph"
    if target.exists() or target.is_symlink():
        raise click.ClickException("graph/ already exists; reuse its authored files. Nothing was changed.")
    template = Path(__file__).resolve().parents[1] / "templates" / "graph"
    try:
        shutil.copytree(template, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    except OSError as exc:
        raise click.ClickException(str(exc)) from exc
    files = sorted(str(path.relative_to(target)) for path in target.rglob("*") if path.is_file())
    if as_json:
        click.echo(json.dumps({"schema_version": 1, "path": str(target), "files": files}, indent=2))
    else:
        click.echo(f"Created graph/ ({len(files)} files)\nEdit graph/pipelines/build_graph.py; see graph/README.md.")


def _pipeline(reference: str) -> Pipeline:
    module, separator, attribute = reference.partition(":")
    if not separator or not module or not attribute:
        raise ValueError("Use a project module:object, e.g. graph.pipelines.build_graph:PIPELINE")
    root = str(Path.cwd())
    if root not in sys.path:
        sys.path.insert(0, root)
    result = getattr(importlib.import_module(module), attribute)
    if not isinstance(result, Pipeline):
        raise ValueError(f"{reference} must be a biotope.graph.Pipeline")
    return result


@graph_group.command()
@click.argument("pipeline")
@click.option(
    "--json", "as_json", is_flag=True, help="Emit topology, requirement coverage, revisions and checker results."
)
def check(pipeline: str, as_json: bool) -> None:
    """Check import-safe definitions and run Pyright; never invoke loaders."""
    from biotope.graph.check import check_pipeline

    try:
        result = check_pipeline(_pipeline(pipeline))
    except (ValueError, OSError, ImportError, AttributeError, TypeError) as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"Definitions and Python types checked: {pipeline}")
        click.echo("No source values or scientific validity checked.")
        for warning in result["warnings"]:
            click.echo(f"Warning: {warning}")
        for key, reason in result["deferrals"].items():
            click.echo(f"Deferred {key}: {reason}")


@graph_group.command()
@click.argument("pipeline")
@click.option(
    "--out",
    required=True,
    type=click.Path(path_type=Path),
    help="New output directory; existing runs are never overwritten.",
)
def build(pipeline: str, out: Path) -> None:
    """Check definitions, then execute the project pipeline and write BioCypher files."""
    from biotope.graph.build import run_pipeline

    click.echo("Checking definitions, then explicitly loading selected source values and building the graph…")
    try:
        result = run_pipeline(_pipeline(pipeline), out)
    except Exception as exc:
        raise click.ClickException(f"{exc}\nRun record, if execution started: {out / 'run.json'}") from exc
    click.echo(
        f"Complete: {result['graph_objects']}\nRun record: {out / 'run.json'}\nProvenance: {out / 'provenance.jsonl'}"
    )
