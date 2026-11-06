"""Change coarse dataset workflow state explicitly, without certifying a graph build."""

from __future__ import annotations

import click

from biotope.commands.add import resolve_dataset_ref
from biotope.croissant import annotation
from biotope.graph.sources import refresh_description, write_description, write_text_atomic
from biotope.metadata import DERIVED_FROM, STATUS, STATUS_VALUES, add_derived_from, get_derived_from, set_status
from biotope.utils import find_biotope_root, warn_ignored


@click.command()
@click.argument("dataset", type=str)
@click.argument("status", type=click.Choice(list(STATUS_VALUES)))
@click.option(
    "--derived-from",
    "derived_from",
    multiple=True,
    help="A dataset this one was derived from, written to prov:wasDerivedFrom; repeatable.",
)
def mark(dataset: str, status: str, derived_from: tuple[str, ...]) -> None:
    """Set the biotope:status of DATASET to STATUS.

    DATASET is a data path, a manifest path or a dataset name, as for biotope add --derived-from.
    """
    biotope_root = find_biotope_root()
    if biotope_root is None:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    try:
        target_id = resolve_dataset_ref(dataset, biotope_root)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc

    manifest_path = biotope_root / ".biotope" / "datasets" / f"{target_id}.jsonld"
    resolved_sources: list[str] = []
    for ref in derived_from:
        try:
            resolved_sources.append(resolve_dataset_ref(ref, biotope_root))
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc

    found = annotation.located(manifest_path)
    try:
        metadata = refresh_description(manifest_path)
        if found is None:
            set_status(metadata, status)
            for source in resolved_sources:
                add_derived_from(metadata, source)
        else:
            lineage = list(dict.fromkeys([*get_derived_from(metadata), *resolved_sources]))
            given = {STATUS: status, **({DERIVED_FROM: lineage} if resolved_sources else {})}
            write_text_atomic(found, annotation.edited(found, (), given))
        metadata = write_description(manifest_path, metadata)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    warn_ignored(biotope_root, [manifest_path, *([found] if found is not None else [])])

    summary = f"✓ {target_id} → {status}"
    new_provenance = [s for s in resolved_sources if s in get_derived_from(metadata)]
    if new_provenance:
        summary += f"  (derived from: {', '.join(new_provenance)})"
    click.echo(summary)
