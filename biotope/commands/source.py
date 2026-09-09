"""Curate Croissant descriptions and generate source-record declarations."""

from pathlib import Path

import click

from biotope.graph.sources import (
    check_source_packages,
    generate_source_packages,
    package_root,
    register_metadata,
)
from biotope.utils import find_biotope_root, stage_git_changes


@click.group(name="source")
def source_group() -> None:
    """Register curated metadata and generate declaration-only Python."""


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


@source_group.command()
@click.argument("metadata", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--out",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Sources package root, e.g. graph/sources.",
)
@click.option("--package", default=None, help="Manifest package name; defaults to the manifest filename.")
@click.option("--check", is_flag=True, help="Check freshness without writing.")
def generate(metadata: Path, out: Path, package: str | None, check: bool) -> None:
    """Generate one source package per record set, with missing registration/loader boilerplate."""
    try:
        statuses = check_source_packages(metadata, out, package)
        created = () if check else generate_source_packages(metadata, out, package, statuses)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    root = package_root(metadata, out, package)
    if check:
        for status in statuses:
            if status.severity != "ok":
                click.echo(f"{status.state.title()}: {status.path}{f' ({status.detail})' if status.detail else ''}")
        blocking = [s for s in statuses if s.severity == "error"]
        if blocking:
            raise click.ClickException(f"{len(blocking)} of {len(statuses)} generated paths need regeneration")
        click.echo(f"Current: {root}")
        return
    inventory = root / "__init__.py"
    packages = sorted({path.parent for path in created} - {root})
    click.echo(f"Generated: {root} ({len(packages)} record sets)")
    # The inventory is always rewritten; only project-owned files are newly created.
    for path in created:
        if path.name != "schema.py" and path != inventory:
            click.echo(f"Created: {path}")
    # Leftovers are reported, never removed: their loaders are authored work.
    for status in statuses:
        if status.severity == "warning":
            click.echo(f"Warning: {status.path} is {status.state}; {status.detail}", err=True)
    click.echo(
        f"Review source types; implement each loader and select from {root.name}.CONTRACTS "
        "into SOURCES in graph/sources/__init__.py."
    )
