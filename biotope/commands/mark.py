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
    help="Add `prov:wasDerivedFrom` pointer (repeatable). Same ref forms as `biotope add --derived-from`.",
)
def mark(dataset: str, status: str, derived_from: tuple[str, ...]) -> None:
    """Set DATASET's biotope:status to STATUS (raw | processed | mapped).

    DATASET accepts a dataset canonical id (rel path), a data path, or a
    manifest path — same resolution as `biotope add --derived-from`.

    Examples::

        biotope mark data/kidney_pdf processed --derived-from data/kidney_extracted
        biotope mark data/ot/target mapped
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
    if not manifest_path.is_file():
        click.echo(f"❌ No manifest at {manifest_path.relative_to(biotope_root)}.")
        raise click.Abort

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
