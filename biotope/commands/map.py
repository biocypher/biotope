from __future__ import annotations

import json
from pathlib import Path

import click
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from biotope.croissant.inspector import inspect_dataset, render_inspection
from biotope.croissant.spec import CroissantDatasetModel, load_from_url
from biotope.graph.sources import refresh_description
from biotope.metadata import resolve_target
from biotope.project_model import Project, find_project
from biotope.utils import find_biotope_root


console = Console()


@click.group(invoke_without_command=True, name="map")
@click.option(
    "--purpose",
    "-p",
    type=str,
    default=None,
    help="Replace the project's purpose: who uses the graph, for which tasks, and the typical questions.",
)
@click.option("--show", is_flag=True, help="Print the project's purpose and exit.")
@click.pass_context
def map_group(ctx: click.Context, purpose: str | None, show: bool) -> None:
    """Record the project's purpose and inspect Croissant metadata."""
    if ctx.invoked_subcommand is not None:
        return
    if purpose is None and not show:
        click.echo(ctx.get_help())
        click.echo(
            "\nDescribe data with biotope add; inspect metadata here. Generate typed sources with "
            "biotope source generate, then author Python mappings and use biotope graph check."
        )
        return
    project_path = find_project()
    if project_path is None:
        raise click.ClickException("No project.yaml found. Run `biotope init <name>` first.")
    try:
        project = Project.load(project_path)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from None
    if purpose is not None:
        project = Project(purpose=purpose)
        project.dump(project_path)
        click.echo(f"Updated {project_path}")
    click.echo(f"purpose: {project.purpose or '(not set)'}")


# ---------------------------------------------------------------------------
# `biotope map inspect`
# ---------------------------------------------------------------------------


@map_group.command()
@click.argument("croissant", type=str)
@click.option("--json", "as_json", is_flag=True, help="Emit a machine-readable JSON inspection.")
def inspect(croissant: str, as_json: bool) -> None:
    """Show declared sources and fields without reading source data."""
    dataset = _load_croissant(croissant)
    inspection = inspect_dataset(
        dataset,
    )
    if as_json:
        click.echo(json.dumps(inspection.to_json(), indent=2, default=str))
        return
    render_inspection(inspection, console)


def _load_croissant(path: str) -> CroissantDatasetModel:
    """Load a Croissant JSON-LD file with a friendly error for common mistakes.

    Accepts three input shapes:

    * a Croissant JSON-LD path or URL (canonical form),
    * a `.biotope.yaml` annotate scaffold path (suggests the right file),
    * a *data directory* that was previously ingested via ``biotope add`` —
      resolved to the canonical ``.biotope/datasets/<rel>.jsonld`` automatically.
    """
    # Keep stdout usable as JSON even when metadata cannot be loaded.
    console = Console(stderr=True)
    if path.startswith(("http://", "https://")):
        try:
            return load_from_url(path)
        except Exception as exc:
            console.print(f"❌ Could not load Croissant file from URL: [cyan]{path}[/cyan]\n   {exc}")
            raise click.Abort from exc

    p = Path(path)
    if not p.exists():
        console.print(f"❌ Croissant file not found: [cyan]{path}[/cyan]")
        raise click.Abort

    if p.is_dir():
        resolved = _resolve_data_dir_to_croissant(p)
        if resolved is None:
            console.print(
                Panel(
                    f"[cyan]{path}[/cyan] is a directory but no Croissant metadata has been "
                    f"generated for it.\n"
                    f"Run [bold]biotope add {path}[/bold] first; the Croissant file will land at "
                    f"[cyan].biotope/datasets/<...>.jsonld[/cyan].",
                    title="No Croissant for this directory",
                    border_style="red",
                )
            )
            raise click.Abort
        path = str(resolved)
        p = resolved

    suffix = p.name.lower()
    if suffix.endswith(".biotope.yaml"):
        root = find_biotope_root()
        data = p.parent if p.name == ".biotope.yaml" else p.with_name(p.name.removesuffix(".biotope.yaml"))
        manifest = resolve_target(data, root).metadata_path if root is not None and data.exists() else None
        console.print(
            Panel(
                "This is an [yellow]annotation file[/yellow], not a Croissant JSON-LD file.\n"
                "`biotope map` expects the Croissant metadata for a dataset, which lives under "
                "[cyan].biotope/datasets/[/cyan].\n\n"
                + (
                    f"Try:  [bold]biotope map inspect {manifest.relative_to(root)}[/bold]"
                    if manifest is not None and root is not None and manifest.is_file()
                    else "Run [bold]biotope add <data>[/bold] first to generate the Croissant file under "
                    "[cyan].biotope/datasets/[/cyan]."
                ),
                title=str(p),
                border_style="red",
            )
        )
        raise click.Abort
    if suffix.endswith((".yaml", ".yml")):
        console.print(
            f"❌ [cyan]{path}[/cyan] looks like YAML, but Croissant metadata is JSON-LD.\n"
            "   Pass a Croissant JSON file from [cyan].biotope/datasets/[/cyan]."
        )
        raise click.Abort

    try:
        return CroissantDatasetModel.model_validate(refresh_description(p))
    except ValueError as exc:
        reason = exc.errors()[0].get("msg", exc) if isinstance(exc, ValidationError) else exc
        console.print(
            Panel(
                f"[cyan]{path}[/cyan] is not a valid Croissant JSON-LD file.\n\n"
                f"Underlying error: {reason}\n\n"
                "Pass a Croissant file from [cyan].biotope/datasets/[/cyan] (created by "
                "`biotope add`).",
                title="Invalid Croissant file",
                border_style="red",
            )
        )
        raise click.Abort from exc


def _resolve_data_dir_to_croissant(data_dir: Path) -> Path | None:
    """Given a data directory, return its canonical Croissant JSON-LD if it exists.

    ``biotope add <data_dir>`` writes the per-directory Croissant at
    ``.biotope/datasets/<same-relative-path>.jsonld``. We resolve that path and
    also fall back to searching for jsonld files mirrored under that subtree.
    """
    project_root = find_biotope_root()
    if project_root is None:
        return None
    try:
        rel = data_dir.resolve().relative_to(project_root.resolve())
    except ValueError:
        return None
    datasets_root = project_root / ".biotope" / "datasets"
    canonical = datasets_root / f"{rel}.jsonld"
    if canonical.is_file():
        return canonical
    nested = sorted((datasets_root / rel).rglob("*.jsonld")) + sorted((datasets_root / rel).rglob("*.croissant.json"))
    return nested[0] if nested else None
