"""``biotope queue`` — the agentic pipeline view.

A derived view over every manifest under ``.biotope/datasets/``. Groups them
by ``biotope:status`` so an agent (or human) resuming a session can see, in
one shot, what's still raw, what's ready to map, and what's already in the KG.

The "raw" section automatically hides any dataset that something else already
``prov:wasDerivedFrom`` — those have been consumed by a downstream artifact
and shouldn't be re-picked-up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import click
from rich.console import Console

from biotope.metadata import (
    STATUS_MAPPED,
    STATUS_PROCESSED,
    STATUS_RAW,
    STATUS_VALUES,
    get_derived_from,
    get_status,
)
from biotope.utils import find_biotope_root

console = Console()


@dataclass(frozen=True)
class _QueueEntry:
    dataset_id: str
    status: str
    derived_from: tuple[str, ...]
    date_created: str | None
    manifest_path: Path


@click.command(name="queue")
@click.option(
    "--status",
    "status_filter",
    type=click.Choice(list(STATUS_VALUES)),
    default=None,
    help="Show only one section.",
)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output for agents.")
@click.option(
    "--sort",
    type=click.Choice(["time", "name"]),
    default="time",
    show_default=True,
    help="Order within each section. 'time' picks the oldest raw first.",
)
def queue(status_filter: str | None, as_json: bool, sort: str) -> None:
    """Show every dataset grouped by pipeline state.

    The agentic queue: raw / processed / mapped, plus anomalies for any
    dangling ``prov:wasDerivedFrom`` pointers.
    """
    biotope_root = find_biotope_root()
    if biotope_root is None:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    entries = _scan_manifests(biotope_root)

    # Hide raw entries that have been consumed (something else derivesFrom them).
    consumed_ids = {src for entry in entries for src in entry.derived_from}
    raw_active = [
        e for e in entries
        if e.status == STATUS_RAW and e.dataset_id not in consumed_ids
    ]
    raw_consumed = [
        e for e in entries
        if e.status == STATUS_RAW and e.dataset_id in consumed_ids
    ]
    processed = [e for e in entries if e.status == STATUS_PROCESSED]
    mapped = [e for e in entries if e.status == STATUS_MAPPED]

    for bucket in (raw_active, raw_consumed, processed, mapped):
        _sort_in_place(bucket, sort)

    # Anomalies: any wasDerivedFrom pointer that doesn't resolve to a known id.
    known_ids = {e.dataset_id for e in entries}
    dangling: list[tuple[str, str]] = []
    for entry in entries:
        for src in entry.derived_from:
            if src not in known_ids:
                dangling.append((entry.dataset_id, src))

    if as_json:
        _emit_json(
            raw_active=raw_active,
            raw_consumed=raw_consumed,
            processed=processed,
            mapped=mapped,
            dangling=dangling,
            status_filter=status_filter,
        )
        return

    _render(
        raw_active=raw_active,
        raw_consumed=raw_consumed,
        processed=processed,
        mapped=mapped,
        dangling=dangling,
        status_filter=status_filter,
    )


def _scan_manifests(biotope_root: Path) -> list[_QueueEntry]:
    datasets_dir = biotope_root / ".biotope" / "datasets"
    if not datasets_dir.is_dir():
        return []
    entries: list[_QueueEntry] = []
    for manifest_path in sorted(datasets_dir.rglob("*.jsonld")):
        try:
            with open(manifest_path) as handle:
                metadata = json.load(handle)
        except (OSError, ValueError):
            continue
        dataset_id = str(
            manifest_path.relative_to(datasets_dir).with_suffix("")
        )
        entries.append(
            _QueueEntry(
                dataset_id=dataset_id,
                status=get_status(metadata),
                derived_from=tuple(get_derived_from(metadata)),
                date_created=metadata.get("dateCreated"),
                manifest_path=manifest_path,
            )
        )
    return entries


def _sort_in_place(entries: list[_QueueEntry], sort: str) -> None:
    if sort == "name":
        entries.sort(key=lambda e: e.dataset_id)
    else:  # time: ascending so the agent processes the oldest raw first.
        entries.sort(key=lambda e: (e.date_created or "", e.dataset_id))


def _render(
    *,
    raw_active: list[_QueueEntry],
    raw_consumed: list[_QueueEntry],
    processed: list[_QueueEntry],
    mapped: list[_QueueEntry],
    dangling: list[tuple[str, str]],
    status_filter: str | None,
) -> None:
    sections = (
        ("RAW", "needs processing", raw_active, "yellow"),
        ("PROCESSED", "ready to map", processed, "cyan"),
        ("MAPPED", "in the KG", mapped, "green"),
    )
    any_emitted = False
    for label, hint, bucket, colour in sections:
        if status_filter and label.lower() != status_filter:
            continue
        any_emitted = True
        # Use no_wrap=True on each print to keep `LABEL (N) — hint` on one
        # line even in narrow CliRunner buffers; section labels are short
        # enough to never need wrapping in real terminals either.
        console.print(
            f"\n[bold {colour}]{label}[/bold {colour}] ({len(bucket)}) — {hint}",
            no_wrap=True,
        )
        if not bucket:
            console.print("  [dim](none)[/dim]")
            continue
        for entry in bucket:
            line = f"  • [bold]{entry.dataset_id}[/bold]"
            if entry.derived_from:
                line += f"  [dim](derived from: {', '.join(entry.derived_from)})[/dim]"
            console.print(line, no_wrap=True)

    # Consumed raw datasets are shown only when no filter is applied, as a
    # small dim section — they're not actionable but they're worth seeing.
    if not status_filter and raw_consumed:
        console.print(
            f"\n[dim]Raw inputs already consumed "
            f"(their derivatives are in the queue): {len(raw_consumed)}[/dim]",
            no_wrap=True,
        )
        for entry in raw_consumed:
            console.print(f"  [dim]• {entry.dataset_id}[/dim]", no_wrap=True)

    if not status_filter and dangling:
        console.print(
            "\n[bold red]ANOMALIES[/bold red] — dangling provenance pointers:",
            no_wrap=True,
        )
        for owner, missing in dangling:
            console.print(
                f"  [red]• {owner} → {missing} (not found)[/red]", no_wrap=True
            )

    if not any_emitted:
        console.print("[dim]No datasets match this filter.[/dim]")


def _emit_json(
    *,
    raw_active: list[_QueueEntry],
    raw_consumed: list[_QueueEntry],
    processed: list[_QueueEntry],
    mapped: list[_QueueEntry],
    dangling: list[tuple[str, str]],
    status_filter: str | None,
) -> None:
    def _serialise(entry: _QueueEntry) -> dict:
        return {
            "id": entry.dataset_id,
            "status": entry.status,
            "derived_from": list(entry.derived_from),
            "date_created": entry.date_created,
        }

    sections = {
        "raw": [_serialise(e) for e in raw_active],
        "processed": [_serialise(e) for e in processed],
        "mapped": [_serialise(e) for e in mapped],
    }
    if status_filter:
        sections = {status_filter: sections.get(status_filter, [])}
    payload = {
        "sections": sections,
        "raw_consumed": [_serialise(e) for e in raw_consumed],
        "anomalies": {
            "dangling_provenance": [
                {"dataset": owner, "missing_source": missing}
                for owner, missing in dangling
            ],
        },
    }
    click.echo(json.dumps(payload, indent=2, default=str))
