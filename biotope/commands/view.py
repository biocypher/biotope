"""``biotope view`` — inspect a built knowledge graph.

v1 promise: print node and edge counts for the most recent ``biotope build``
output. Future scope: sample queries, schema diff against
``.biotope/config.yaml``, integration with `biocypher view`.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from biotope.project_model import find_project

console = Console()


@click.command()
@click.option(
    "--build-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to a build/ directory. Default: <project_root>/build.",
)
def view(build_dir: Path | None) -> None:
    """Print summary statistics for the most recent build."""
    if build_dir is None:
        project_path = find_project()
        if project_path is None:
            click.echo("❌ No project.yaml found. Pass --build-dir or run `biotope init` first.")
            raise click.Abort
        project_root = (
            project_path.parent.parent if project_path.parent.name == ".biotope" else project_path.parent
        )
        build_dir = project_root / "build"
        if not build_dir.is_dir():
            click.echo(f"❌ No build/ directory at {build_dir}. Run `biotope build` first.")
            raise click.Abort

    output_dir = build_dir / "biocypher-out"
    if not output_dir.is_dir():
        console.print(f"[yellow]No biocypher-out/ yet at {output_dir}.[/yellow]")
        console.print("Run [bold]python create_knowledge_graph.py[/bold] inside the build dir first.")
        return

    table = Table(title="BioCypher build summary")
    table.add_column("file")
    table.add_column("lines", justify="right")
    table.add_column("kind")

    total_nodes = 0
    total_edges = 0
    for csv_file in sorted(output_dir.rglob("*-part*.csv")):
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
