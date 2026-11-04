from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import click
import yaml

from biotope.utils import find_biotope_root


@click.group(help="Manage the project metadata that biotope add applies to every dataset.")
def config() -> None:
    pass


@config.command(
    "set-project-metadata",
    help="Set project metadata in .biotope/config.yaml. Give only values the user confirmed for every dataset; "
    "a dataset's annotation file overrides them. An empty value removes the field.",
)
@click.option("--description", help="What the project is about.")
@click.option("--url", help="The project's web page.")
@click.option("--creator", help="The contact person for every dataset, when the user names one for the project.")
@click.option("--license", "license_", help="The licence URL of every dataset.")
@click.option("--citation", help="How to cite every dataset.")
@click.option("--access-restrictions", help="Access restrictions of every dataset.")
@click.option("--legal-obligations", help="Legal obligations of every dataset.")
@click.option("--collaboration-partner", help="The collaboration partner and institute.")
def set_project_metadata(license_: str | None, **given: str | None) -> None:
    root = _root()
    changes = {key: value.strip() for key, value in {**given, "license": license_}.items() if value is not None}
    if not changes:
        raise click.UsageError("Give at least one field, such as --license.")
    path = root / ".biotope/config.yaml"
    settings = _read(path)
    metadata = cast(dict[str, Any], settings.get("project_metadata") or {})
    for key, value in changes.items():
        if value:
            metadata[key] = value
        else:
            metadata.pop(key, None)
    settings["project_metadata"] = metadata
    if not metadata:
        del settings["project_metadata"]
    path.write_text(yaml.safe_dump(settings, sort_keys=False, allow_unicode=True), encoding="utf-8")
    _show(metadata)


@config.command("show-project-metadata", help="Show the project metadata that biotope add applies to every dataset.")
def show_project_metadata() -> None:
    _show(cast(dict[str, Any], _read(_root() / ".biotope/config.yaml").get("project_metadata") or {}))


def _root() -> Path:
    root = find_biotope_root()
    if root is None:
        raise click.ClickException("Not in a biotope project. Run 'biotope init' first.")
    return root


def _read(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    return cast(dict[str, Any], loaded) if isinstance(loaded, dict) else {}


def _show(metadata: dict[str, Any]) -> None:
    if not metadata:
        click.echo("No project metadata set.")
    for key, value in metadata.items():
        click.echo(f"{key}: {value}")
