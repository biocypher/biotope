from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import click

from biotope.croissant import annotation
from biotope.graph.sources import refresh_description, write_description, write_text_atomic
from biotope.metadata import resolve_target
from biotope.utils import find_biotope_root, warn_ignored


@click.group(invoke_without_command=True)
@click.pass_context
def annotate(ctx: click.Context) -> None:
    """Write what people know about a dataset into its annotation file, and validate descriptions."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.fail("Missing command.")


@annotate.command(name="set")
@click.argument("data", type=click.Path(exists=True, path_type=Path))
@click.argument("values", nargs=-1, required=True)
@click.option("--table", help="A table's ID, such as push/people.csv#people.")
@click.option("--column", help="A column of --table, by its name in the data.")
def set_values(data: Path, values: tuple[str, ...], table: str | None, column: str | None) -> None:
    """Write KEY=VALUE pairs into the annotation file of DATA, a dataset biotope add described.

    Without --table the values describe the dataset, with --table that table, and with --column that column.
    A repeated KEY makes a list, and an empty VALUE clears what the data says. A table's key names its
    columns, as in key=person_id; an equivalent property is a URL, as in equivalentProperty=https://schema.org/name.
    """
    root = find_biotope_root()
    if root is None:
        raise click.ClickException("Not in a biotope project. Run 'biotope init' first.")
    if column is not None and table is None:
        raise click.BadParameter("--column needs --table")
    given = _pairs(values, reserved={annotation.TABLES, annotation.FILE_SETS} if table is None else set())
    if column is None and table is not None and annotation.COLUMNS in given:
        raise click.BadParameter("name a column with --column")
    target = resolve_target(data, root)
    if not target.metadata_path.is_file():
        raise click.ClickException(f"{data} is not a dataset; describe it with biotope add {data}")
    try:
        description = refresh_description(target.metadata_path)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if table is not None:
        _check_names(description, table, [column] if column is not None else annotation.names(given.get("key")))
    scope = () if table is None else (annotation.TABLES, table)
    scope += () if column is None else (annotation.COLUMNS, column)
    path = annotation.annotation_path(data.resolve())
    try:
        write_text_atomic(path, annotation.edited(path, scope, given))
        write_description(target.metadata_path, description)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    warn_ignored(root, [path, target.metadata_path])
    click.echo(f"Annotated {path.relative_to(root)}")


def _pairs(values: tuple[str, ...], *, reserved: set[str]) -> dict[str, Any]:
    given: dict[str, Any] = {}
    for pair in values:
        key, separator, value = pair.partition("=")
        key = key.strip()
        if not separator or not key:
            raise click.BadParameter(f"{pair!r}: expected KEY=VALUE")
        if key in reserved:
            raise click.BadParameter(f"{key!r} holds tables or file sets; use --table, or edit the annotation file")
        if key in given:
            previous = given[key]
            given[key] = [*(previous if isinstance(previous, list) else [previous]), value]
        else:
            given[key] = value
    return given


def _check_names(description: dict[str, Any], table: str, columns: list[str]) -> None:
    record = next((item for item in description.get("recordSet") or [] if item.get("@id") == table), None)
    if record is None:
        raise click.ClickException(f"The description has no table {table!r}")
    missing = [name for name in columns if name not in annotation.columns(record)]
    if missing:
        raise click.ClickException(f"The table {table!r} has no column {', '.join(map(repr, missing))}")


@annotate.command()
@click.option(
    "--jsonld",
    "-j",
    type=click.Path(exists=True),
    required=True,
    help="Path to the JSON-LD metadata file to validate.",
)
def validate(jsonld):
    """Validate a Croissant metadata file."""
    try:
        # Use mlcroissant CLI to validate the file
        result = subprocess.run(
            ["mlcroissant", "validate", "--jsonld", jsonld],
            capture_output=True,
            text=True,
            check=True,
        )
        click.echo("Validation successful! The metadata file is valid.")
        if result.stdout:
            # Filter out informational log messages
            filtered_output = "\n".join(
                line for line in result.stdout.splitlines() if not line.startswith("I") or not line.endswith("Done.")
            )
            if filtered_output:
                click.echo(f"Output: {filtered_output}")
        if result.stderr:
            # Filter out informational log messages
            filtered_stderr = "\n".join(
                line for line in result.stderr.splitlines() if not line.startswith("I") or not line.endswith("Done.")
            )
            if filtered_stderr:
                click.echo(f"Warnings: {filtered_stderr}")
    except subprocess.CalledProcessError as e:
        click.echo(f"Validation failed: {e.stderr}", err=True)
        exit(1)
    except Exception as e:
        click.echo(f"Error running validation: {e!s}", err=True)
        exit(1)
