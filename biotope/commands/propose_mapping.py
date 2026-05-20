"""``biotope propose-mapping`` — heuristic ``mapping.yaml`` from a Croissant file."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from biotope.croissant.api import propose_mapping as _propose
from biotope.project_model import find_project

console = Console()


@click.command(name="propose-mapping")
@click.argument("croissant_path", type=str)
@click.option(
    "--out",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the proposed mapping to this path. Default: infer mappings/<name>.mapping.yaml when possible.",
)
@click.option(
    "--stdout",
    "to_stdout",
    is_flag=True,
    help="Print the scaffold to stdout instead of writing an inferred file.",
)
@click.option(
    "--preview-rows",
    type=click.IntRange(min=0),
    default=3,
    show_default=True,
    help="Number of sample rows to embed as review comments per record set.",
)
def propose_mapping(croissant_path: str, out: Path | None, to_stdout: bool, preview_rows: int) -> None:
    """Propose a heuristic mapping.yaml for a Croissant JSON-LD file.

    Output is the default mapping: one RecordSet per node type, foreign-key
    fields as edges. Refine by hand or via the agent before passing to build.
    """
    if out is not None and to_stdout:
        raise click.UsageError("Choose either --out or --stdout, not both.")

    target = out
    if target is None and not to_stdout:
        target = _default_output_path(croissant_path)
        if target is not None:
            target.parent.mkdir(parents=True, exist_ok=True)

    result = _propose(croissant_path, write_to=target, preview_rows=preview_rows)
    if target:
        console.print(f"✅ Wrote {target}")
    else:
        click.echo(result["yaml"], nl=False)


def _default_output_path(croissant_path: str) -> Path | None:
    if croissant_path.startswith(("http://", "https://")):
        return None

    path = Path(croissant_path).resolve()
    project_root = _project_root_from_croissant_path(path) or _project_root_from_cwd()
    if project_root is None:
        return None

    return project_root / "mappings" / f"{_mapping_stem(path)}.mapping.yaml"


def _project_root_from_croissant_path(path: Path) -> Path | None:
    for parent in path.parents:
        if parent.name == "datasets" and parent.parent.name == ".biotope":
            return parent.parent.parent
    return None


def _project_root_from_cwd() -> Path | None:
    project_path = find_project()
    if project_path is None:
        return None
    return project_path.parent.parent if project_path.parent.name == ".biotope" else project_path.parent


def _mapping_stem(path: Path) -> str:
    name = path.name
    for suffix in (".croissant.json", ".jsonld", ".json", ".yaml", ".yml"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem
