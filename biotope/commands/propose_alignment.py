"""``biotope propose-alignment`` — cross-Croissant equivalence proposals."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console

from biotope.croissant.api import propose_alignment as _propose

console = Console()


@click.command(name="propose-alignment")
@click.argument("mappings", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--out",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the proposed alignment to this path. Default: stdout only.",
)
def propose_alignment(mappings: tuple[Path, ...], out: Path | None) -> None:
    """Propose an alignment.yaml from N mapping.yaml files.

    Heuristic: shared property names between two nodes suggest a same_node
    equivalence. Human review expected before passing to build.
    """
    result = _propose(list(mappings), write_to=out)
    if out:
        console.print(f"✅ Wrote {out}")
    click.echo(json.dumps(result["alignment"], indent=2, default=str))
