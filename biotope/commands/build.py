"""``biotope build`` — materialise a runnable BioCypher project from mappings.

Reads every ``mappings/*.mapping.yaml`` in the project, optionally an
``alignment.yaml`` at the project root, and emits a ``build/`` directory
containing ``config/schema_config.yaml``, the materialised mappings, and a
``create_knowledge_graph.py`` entry point that streams nodes and edges via
DuckDB into BioCypher.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console

from biotope.croissant.api import materialize
from biotope.project_model import find_project

console = Console()


@click.command()
@click.option(
    "--mappings-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Directory of mapping YAML files. Default: <project_root>/mappings.",
)
@click.option(
    "--alignment",
    "alignment_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to alignment.yaml. Default: <project_root>/alignment.yaml if present.",
)
@click.option(
    "--out",
    "-o",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to materialise the BioCypher project. Default: <project_root>/build.",
)
def build(mappings_dir: Path | None, alignment_path: Path | None, out_dir: Path | None) -> None:
    """Build a deterministic BioCypher project from this biotope's mappings."""
    project_path = find_project()
    if project_path is None:
        click.echo("❌ No project.yaml found. Run `biotope init <name>` first.")
        raise click.Abort
    project_root = (
        project_path.parent.parent if project_path.parent.name == ".biotope" else project_path.parent
    )

    mappings_dir = mappings_dir or (project_root / "mappings")
    mapping_paths = _discover_mapping_paths(mappings_dir)

    if not mapping_paths:
        click.echo(f"❌ No mapping YAML files found under {mappings_dir}.")
        click.echo("   Run `biotope propose-mapping <croissant.json>` first.")
        raise click.Abort

    if alignment_path is None:
        candidate = project_root / "alignment.yaml"
        if candidate.is_file():
            alignment_path = candidate

    out_dir = out_dir or (project_root / "build")
    result = materialize(out_dir, mapping_paths, alignment_path)

    console.print(f"✅ Built BioCypher project at [cyan]{out_dir}[/cyan]")
    click.echo(json.dumps(result, indent=2, default=str))


def _discover_mapping_paths(mappings_dir: Path) -> list[Path]:
    """Return mapping YAML paths, preferring `*.mapping.yaml` over `*.yaml` duplicates."""
    candidates = sorted(mappings_dir.glob("*.yaml")) + sorted(mappings_dir.glob("*.yml"))
    selected: dict[str, Path] = {}

    for path in candidates:
        key = _mapping_identity(path)
        existing = selected.get(key)
        if existing is None or _mapping_path_rank(path) > _mapping_path_rank(existing):
            selected[key] = path

    return list(selected.values())


def _mapping_identity(path: Path) -> str:
    name = path.name
    for suffix in (".mapping.yaml", ".mapping.yml", ".yaml", ".yml"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _mapping_path_rank(path: Path) -> int:
    name = path.name
    if name.endswith((".mapping.yaml", ".mapping.yml")):
        return 2
    if name.endswith((".yaml", ".yml")):
        return 1
    return 0
