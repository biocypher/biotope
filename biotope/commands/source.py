"""Curate Croissant descriptions and generate source-record declarations."""

from pathlib import Path

import click

from biotope.graph.sources import check_generated, generate_source_package, register_metadata
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
    type=click.Path(dir_okay=False, path_type=Path),
    help="Generated module, e.g. graph/sources/study/schema.py.",
)
@click.option("--check", is_flag=True, help="Check freshness without writing.")
def generate(metadata: Path, out: Path, check: bool) -> None:
    """Generate source types and create missing registration/loader boilerplate."""
    created: tuple[Path, ...] = ()
    try:
        if check:
            check_generated(metadata, out)
        else:
            created = generate_source_package(metadata, out)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{'Current' if check else 'Generated'}: {out}")
    for path in created[1:]:
        click.echo(f"Created: {path}")
    if not check:
        click.echo("Review source types; implement the loader and add SOURCE to graph/sources/__init__.py.")
