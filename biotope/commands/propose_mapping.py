"""``biotope propose-mapping`` — deprecated alias for ``biotope map scaffold``.

The original heuristic ``propose-mapping`` has been replaced by an
unresolved-scaffold generator under the new ``biotope map`` command group.
This file remains a thin compatibility shim that prints a deprecation notice
and forwards to :func:`biotope.croissant.api.scaffold_mapping`.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from biotope.croissant.api import scaffold_mapping
from biotope.project_model import Project, find_project


console = Console()


@click.command(name="propose-mapping")
@click.argument("croissant_path", type=str)
@click.option(
    "--out",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the proposed scaffold to this path. Default: mappings/<name>.mapping.yaml.",
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
    help="Sample rows to embed in the inspector comment appendix.",
)
def propose_mapping(croissant_path: str, out: Path | None, to_stdout: bool, preview_rows: int) -> None:
    """Generate an unresolved mapping scaffold for a Croissant JSON-LD file.

    [deprecated] Use ``biotope map scaffold`` instead.
    """
    console.print("[yellow]ℹ `biotope propose-mapping` is deprecated; use `biotope map scaffold` instead.[/yellow]")
    if out is not None and to_stdout:
        raise click.UsageError("Choose either --out or --stdout, not both.")

    # Validate the path with the same friendly error messages as `biotope map scaffold`.
    from biotope.commands.map import _load_croissant

    _load_croissant(croissant_path)

    target = out
    if target is None and not to_stdout:
        target = _default_output_path(croissant_path)
        if target is not None:
            target.parent.mkdir(parents=True, exist_ok=True)

    project = _load_project_optional()
    result = scaffold_mapping(
        croissant_path,
        required_entities=list(project.required_entities) if project else [],
        required_relations=list(project.required_relations) if project else [],
        purpose=project.purpose if project else None,
        write_to=target,
        preview_rows=preview_rows,
    )
    if target:
        console.print(f"✅ Wrote {target}")
    else:
        click.echo(result["yaml"], nl=False)


def _load_project_optional() -> Project | None:
    project_path = find_project()
    if project_path is None:
        return None
    try:
        return Project.load(project_path)
    except Exception:
        return None


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
