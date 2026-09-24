"""Curate Croissant descriptions and scaffold project-owned source packages."""

import os
from pathlib import Path

import click

from biotope.graph.inventory import PackageStatus, SourcePlan, apply_plan, plan_sources, record_revisions, unrecorded
from biotope.graph.revisions import DRIFT_LINE_LIMIT, STORE, short_revision
from biotope.graph.sources import KINDS, register_metadata
from biotope.utils import find_biotope_root, stage_git_changes


@click.group(name="source")
def source_group() -> None:
    """Register curated metadata and scaffold project-owned source packages."""


@source_group.command(name="register")
@click.argument("metadata", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--name", required=True, help="Managed dataset name/path, without .jsonld.")
@click.option("--reason", required=True, help="Review evidence and known gaps.")
@click.option("--replace", is_flag=True, help="Replace this managed description after reviewing corrections.")
def register(metadata: Path, name: str, reason: str, replace: bool) -> None:
    """Register authored Croissant, protecting it from subsequent rebakes."""
    root = find_biotope_root()
    if root is None:
        raise click.ClickException("Run biotope init first")
    try:
        target = register_metadata(
            root,
            metadata,
            name,
            reason=reason,
            replace=replace,
            on_warning=lambda message: click.echo(f"Warning: {message}", err=True),
        )
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    stage_git_changes(root)
    click.echo(f"Registered curated metadata: {target}\nReview source contracts and regenerate before building.")


def _shown(path: Path) -> str:
    relative = os.path.relpath(path.absolute(), Path.cwd())
    return path.as_posix() if relative.startswith("..") else Path(relative).as_posix()


LABEL_WIDTH = 10


def _row(label: str, subject: str, detail: str = "", *, err: bool = False) -> None:
    click.echo(f"{label:<{LABEL_WIDTH - 1}} {subject}", err=err)
    for line in detail.splitlines():
        click.echo(" " * LABEL_WIDTH + line, err=err)


def _describe(status: PackageStatus) -> str:
    lines: list[str] = []
    if status.identity is not None and status.kind is not None:
        lines.append(f"{KINDS[status.kind].label} {status.identity!r}")
    if status.detail:
        lines.append(status.detail)
    if status.drift is not None:
        lines.append(f"acknowledged {short_revision(status.acknowledged)}, manifest {short_revision(status.revision)}")
        lines.extend(status.drift.lines(DRIFT_LINE_LIMIT))
    return "\n".join(lines)


def _report(plan: SourcePlan, *, written: bool) -> None:
    labels = {
        "created": "Created" if written else "Would create",
        "completed": "Completed" if written else "Would complete",
        "current": "Current",
        "drift": "Drift",
        "orphaned": "Orphaned",
        "conflict": "Conflict",
    }
    for status in plan.statuses:
        _row(labels[status.state], _shown(status.path), "" if status.state == "current" else _describe(status))
    for path in plan.generated_files:
        _row("Wrote" if written else "Would write", _shown(path))


@source_group.command()
@click.argument("metadata", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Sources package, e.g. graph/sources.",
)
@click.option("--package", default=None, help="Root package for this manifest; defaults to the manifest filename.")
@click.option("--check", is_flag=True, help="Report what generation would change, without writing.")
def generate(metadata: Path, out: Path, package: str | None, check: bool) -> None:
    """Reconcile one manifest with its source packages; create only what is missing.

    Every described RecordSet, and every file no RecordSet reads, gets a package
    with a schema, a registration and a placeholder loader. Existing schemas,
    registrations and loaders are never rewritten. Drift, orphans and conflicts
    are reported; on a conflict nothing is written.
    """
    try:
        plan = plan_sources(metadata, out, package)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    _row("Generate" if not check else "Check", f"{_shown(metadata)} -> {_shown(plan.root)}")
    if plan.store is None:
        _row(
            "Warning",
            _shown(metadata),
            "not inside a Biotope project, so no contract history is kept and drift cannot be itemized",
            err=True,
        )
    if check or plan.conflicts:
        _report(plan, written=False)
        for status in unrecorded(plan) if check else ():
            _row(
                "Warning",
                _shown(status.path),
                f"revision {short_revision(status.revision)} is acknowledged but not recorded in {STORE}; "
                "run biotope source generate without --check",
                err=True,
            )
        if plan.conflicts:
            raise click.ClickException(f"{len(plan.conflicts)} conflict(s); nothing was written")
        if plan.changes:
            raise click.ClickException("Generation would change the source packages; run it without --check")
        _row("Done", "current")
        return
    try:
        apply_plan(plan)
        recorded = record_revisions(plan)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    _report(plan, written=True)
    if plan.store is not None:
        _row("Recorded", f"{len(recorded)} new of {len(plan.targets)} revisions in {_shown(plan.store.directory)}")
        if recorded:
            stage_git_changes(plan.store.project)
    if any(status.state in ("created", "completed") for status in plan.statuses):
        click.echo(
            "Next: implement each placeholder loader, then select sources from INVENTORY or exclude them "
            "with a reason in graph/sources/__init__.py."
        )
