"""``biotope propose-mapping`` — heuristic ``mapping.yaml`` from a Croissant file."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console

from biotope.croissant.api import propose_mapping as _propose

console = Console()


@click.command(name="propose-mapping")
@click.argument("croissant_path", type=str)
@click.option(
    "--out",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the proposed mapping to this path. Default: stdout only.",
)
def propose_mapping(croissant_path: str, out: Path | None) -> None:
    """Propose a heuristic mapping.yaml for a Croissant JSON-LD file.

    Output is the default mapping: one RecordSet per node type, foreign-key
    fields as edges. Refine by hand or via the agent before passing to build.
    """
    result = _propose(croissant_path, write_to=out)
    if out:
        console.print(f"✅ Wrote {out}")
    click.echo(json.dumps(result["mapping"], indent=2, default=str))
