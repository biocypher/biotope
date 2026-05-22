"""``biotope mark`` — set a dataset's biotope:status (and optional provenance).

The happy path is automatic: `biotope add` classifies raw vs. processed from
the baked Croissant, and the map wizard flips to `mapped` on resolved save.
`mark` is the explicit override — useful when the heuristic is wrong, when an
agent finishes processing a raw input without going through the wizard, or
when status needs to be rolled back after a de-resolve.
"""

from __future__ import annotations

import json

import click
from rich.console import Console

from biotope.commands.add import _resolve_dataset_ref
from biotope.metadata import (
    STATUS_VALUES,
    add_derived_from,
    get_derived_from,
    set_status,
)
from biotope.utils import find_biotope_root


console = Console()


@click.command()
@click.argument("dataset", type=str)
@click.argument("status", type=click.Choice(list(STATUS_VALUES)))
@click.option(
    "--derived-from",
    "derived_from",
    multiple=True,
    help="Add `prov:wasDerivedFrom` pointer (repeatable). Same ref forms as " "`biotope add --derived-from`.",
)
def mark(dataset: str, status: str, derived_from: tuple[str, ...]) -> None:
    """Set DATASET's biotope:status to STATUS (raw | processed | mapped).

    DATASET accepts a dataset canonical id (rel path), a data path, or a
    manifest path — same resolution as `biotope add --derived-from`.

    Examples::

        biotope mark data/raw/kidney_pdf processed --derived-from data/processed/kidney_extracted
        biotope mark data/ot/target mapped
    """
    biotope_root = find_biotope_root()
    if biotope_root is None:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    try:
        target_id = _resolve_dataset_ref(dataset, biotope_root)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc

    manifest_path = biotope_root / ".biotope" / "datasets" / f"{target_id}.jsonld"
    if not manifest_path.is_file():
        click.echo(f"❌ No manifest at {manifest_path.relative_to(biotope_root)}.")
        raise click.Abort

    resolved_sources: list[str] = []
    for ref in derived_from:
        try:
            resolved_sources.append(_resolve_dataset_ref(ref, biotope_root))
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc

    with open(manifest_path) as handle:
        metadata = json.load(handle)
    set_status(metadata, status)
    for source in resolved_sources:
        add_derived_from(metadata, source)
    with open(manifest_path, "w") as handle:
        json.dump(metadata, handle, indent=2)

    summary = f"[green]✓[/green] [cyan]{target_id}[/cyan] → [bold]{status}[/bold]"
    new_provenance = [s for s in resolved_sources if s in get_derived_from(metadata)]
    if new_provenance:
        summary += f"  (derived from: {', '.join(new_provenance)})"
    console.print(summary)
