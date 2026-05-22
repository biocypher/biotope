"""``biotope view`` — inspect a project and any built knowledge graph.

Always surfaces the project's competence questions (`purpose`,
`required_entities`, `required_relations`) at the top so the user can see
what's hidden in the dotfolder. Then prints node and edge counts for the
most recent `biotope build` output, if one exists.

Future scope: sample queries, schema diff against `.biotope/config.yaml`,
integration with `biocypher view`.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from biotope.project_model import Project, find_project


console = Console()


def _project_root_from(path: Path) -> Path:
    return path.parent.parent if path.parent.name == ".biotope" else path.parent


def _render_project_header(project_path: Path) -> None:
    project = Project.load(project_path)
    lines = [
        f"[bold]name:[/bold] {project.name}",
        f"[bold]purpose:[/bold] {project.purpose or '[dim](not set — run `biotope describe --purpose ...`)[/dim]'}",
        f"[bold]required entities:[/bold] {', '.join(project.required_entities) or '[dim](none)[/dim]'}",
        f"[bold]required relations:[/bold] {', '.join(project.required_relations) or '[dim](none)[/dim]'}",
    ]
    if project.data_sources:
        lines.append(f"[bold]data sources:[/bold] {', '.join(project.data_sources)}")
    if project.notes:
        lines.append(f"[bold]notes:[/bold] {project.notes}")
    console.print(
        Panel("\n".join(lines), title=str(project_path), border_style="cyan", expand=False),
    )


def _render_build_summary(build_dir: Path) -> None:
    output_dir = build_dir / "biocypher-out"
    if not output_dir.is_dir():
        console.print(f"\n[yellow]No biocypher-out/ yet at {output_dir}.[/yellow]")
        console.print("Run [bold]python create_knowledge_graph.py[/bold] inside the build dir first.")
        return

    table = Table(title=f"BioCypher build: {build_dir}")
    table.add_column("file")
    table.add_column("lines", justify="right")
    table.add_column("kind")

    total_nodes = 0
    total_edges = 0
    # BioCypher 0.14+ emits a single `<label>.csv` per label; older versions
    # emit one or more `<label>-partNNN.csv` files plus a `<label>-header.csv`.
    # Globbing both forms (and skipping header-only files) lets `view` work
    # against any version. Header files have no data rows; counting them as
    # "-1 lines" understated the total before — exclude them entirely.
    csv_files = [p for p in output_dir.rglob("*.csv") if not p.name.endswith("-header.csv")]
    for csv_file in sorted(csv_files):
        try:
            with csv_file.open() as f:
                count = sum(1 for _ in f) - 1  # subtract header
        except OSError:
            count = -1
        kind = "edge" if "edge" in csv_file.name.lower() else "node"
        table.add_row(csv_file.name, str(count), kind)
        if kind == "node":
            total_nodes += max(0, count)
        else:
            total_edges += max(0, count)

    console.print(table)
    console.print(f"\nTotal nodes: [cyan]{total_nodes}[/cyan]  edges: [cyan]{total_edges}[/cyan]")


@click.command()
@click.option(
    "--build-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to a build/ directory. Default: <project_root>/build.",
)
@click.option(
    "--no-header",
    is_flag=True,
    default=False,
    help="Suppress the project.yaml summary panel.",
)
def view(build_dir: Path | None, no_header: bool) -> None:
    """Show the project's competence questions and any recent build's stats."""
    project_path = find_project()

    if not no_header:
        if project_path is None:
            console.print("[yellow]No project.yaml found in cwd or ancestors.[/yellow]")
        else:
            _render_project_header(project_path)

    if build_dir is None:
        if project_path is None:
            return
        candidate = _project_root_from(project_path) / "build"
        if not candidate.is_dir():
            console.print(f"\n[dim]No build/ directory at {candidate}. Run `biotope build` first.[/dim]")
            return
        build_dir = candidate

    _render_build_summary(build_dir)
