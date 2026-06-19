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

from biotope.croissant.biocypher_labels import schema_term_to_csv_stem
from biotope.croissant.build_runtime import load_build_metrics
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


def _load_edge_csv_stems(schema_config_path: Path) -> set[str] | None:
    """Return CSV basename stems for schema entries BioCypher writes as edges.

    BioCypher names files from schema *terms* (YAML keys) in PascalCase, not
    from ``input_label``. Returns ``None`` when the config can't be read.
    """
    if not schema_config_path.is_file():
        return None
    try:
        import yaml

        config = yaml.safe_load(schema_config_path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return None
    stems: set[str] = set()
    for schema_term, entry in config.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("represented_as") == "edge" and isinstance(schema_term, str):
            stems.add(schema_term_to_csv_stem(schema_term))
    return stems


def _load_active_target(build_dir: Path) -> str | None:
    """Read the active ``dbms`` out of the build's biocypher_config.yaml."""
    config_path = build_dir / "config" / "biocypher_config.yaml"
    if not config_path.is_file():
        return None
    try:
        import yaml

        config = yaml.safe_load(config_path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return None
    dbms = config.get("biocypher", {}).get("dbms")
    return str(dbms) if dbms is not None else None


def _render_build_summary(build_dir: Path) -> None:
    target = _load_active_target(build_dir)
    if target is not None:
        console.print(f"\n[bold]target (dbms):[/bold] {target}")

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
    # Consult schema_config.yaml: edge CSV stems are PascalCase schema terms.
    edge_stems = _load_edge_csv_stems(build_dir / "config" / "schema_config.yaml")
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
        stem = csv_file.stem.split("-part")[0]
        if edge_stems is not None:
            kind = "edge" if stem in edge_stems else "node"
        else:
            kind = "edge" if "edge" in csv_file.name.lower() else "node"
        table.add_row(csv_file.name, str(count), kind)
        if kind == "node":
            total_nodes += max(0, count)
        else:
            total_edges += max(0, count)

    console.print(table)
    console.print(f"\nTotal nodes: [cyan]{total_nodes}[/cyan]  edges: [cyan]{total_edges}[/cyan]")

    metrics = load_build_metrics(build_dir)
    if metrics is not None:
        orphaned = metrics.get("orphaned_count", 0)
        total = metrics.get("total_edges", 0)
        importable = metrics.get("importable_edges", 0)
        console.print(
            f"Orphaned edges: [cyan]{orphaned}[/cyan] / {total} "
            f"([cyan]{importable}[/cyan] importable)",
        )
        compile_drops = metrics.get("compile_drops")
        if isinstance(compile_drops, dict) and any(compile_drops.values()):
            dropped_nodes = compile_drops.get("dropped_nodes_non_scalar", 0)
            dropped_edges = compile_drops.get("dropped_edges_non_scalar", 0)
            console.print(
                f"Compile drops: [cyan]{dropped_nodes}[/cyan] nodes, "
                f"[cyan]{dropped_edges}[/cyan] edges (non-scalar ids)",
            )


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
