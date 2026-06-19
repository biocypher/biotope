"""``biotope propose-alignment`` — cross-Croissant equivalence proposals."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from biotope.croissant.api import propose_alignment as _propose
from biotope.project_model import find_project


console = Console()


@click.command(name="propose-alignment")
@click.argument("mappings", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--out",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the proposed alignment to this path. Default: infer alignment.yaml when possible.",
)
@click.option(
    "--stdout",
    "to_stdout",
    is_flag=True,
    help="Print the proposed alignment YAML to stdout instead of writing an inferred file.",
)
def propose_alignment(mappings: tuple[Path, ...], out: Path | None, to_stdout: bool) -> None:
    """Propose an alignment.yaml from N mapping.yaml files.

    Heuristic: shared property names between two nodes suggest a same_node
    equivalence. Human review expected before passing to build.
    """
    if out is not None and to_stdout:
        raise click.UsageError("Choose either --out or --stdout, not both.")

    target = out
    if target is None and not to_stdout:
        target = _default_output_path(mappings)

    result = _propose(list(mappings), write_to=target)
    if target is not None:
        console.print(f"✅ Wrote {target}")
    else:
        click.echo(result["yaml"], nl=False)
    if result.get("reason"):
        console.print(f"[yellow]Note:[/yellow] {result['reason']}")


def _default_output_path(mappings: tuple[Path, ...]) -> Path | None:
    project_root = _project_root_from_mappings(mappings) or _project_root_from_cwd()
    if project_root is None:
        return None
    return project_root / "alignment.yaml"


def _project_root_from_mappings(mappings: tuple[Path, ...]) -> Path | None:
    roots: set[Path] = set()
    for mapping_path in mappings:
        resolved = mapping_path.resolve()
        for parent in resolved.parents:
            if parent.name == "mappings":
                roots.add(parent.parent)
                break
    if len(roots) == 1:
        return next(iter(roots))
    return None


def _project_root_from_cwd() -> Path | None:
    project_path = find_project()
    if project_path is None:
        return None
    return project_path.parent.parent if project_path.parent.name == ".biotope" else project_path.parent
