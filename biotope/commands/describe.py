"""``biotope describe`` — mutate ``.biotope/project.yaml`` non-interactively.

This is the canonical way for an agent (or scripting user) to record content
intent. All fields are flag-driven; list-valued flags can be repeated.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import click
from rich.console import Console

from biotope.project_model import Project, find_project, resolve_project_path

console = Console()


@click.command()
@click.option("--purpose", "-p", type=str, default=None, help="Replace the project's purpose statement.")
@click.option(
    "--entity",
    "-e",
    "entities",
    multiple=True,
    help="Add to required_entities. Repeatable. Use --clear-entities to reset first.",
)
@click.option(
    "--relation",
    "-r",
    "relations",
    multiple=True,
    help="Add to required_relations. Repeatable.",
)
@click.option(
    "--source",
    "-s",
    "sources",
    multiple=True,
    help="Add to data_sources. Repeatable.",
)
@click.option("--notes", type=str, default=None, help="Replace the notes field.")
@click.option("--clear-entities", is_flag=True, help="Empty required_entities before adding --entity values.")
@click.option("--clear-relations", is_flag=True, help="Empty required_relations before adding --relation values.")
@click.option("--clear-sources", is_flag=True, help="Empty data_sources before adding --source values.")
@click.option(
    "--edit",
    is_flag=True,
    help="Open $EDITOR on project.yaml instead of applying flags.",
)
@click.option(
    "--show",
    is_flag=True,
    help="Print the current project.yaml contents and exit. No mutation.",
)
def describe(
    purpose: str | None,
    entities: tuple[str, ...],
    relations: tuple[str, ...],
    sources: tuple[str, ...],
    notes: str | None,
    clear_entities: bool,
    clear_relations: bool,
    clear_sources: bool,
    edit: bool,
    show: bool,
) -> None:
    """Read or update the project's competence-questions document."""
    project_path = find_project()
    if project_path is None:
        click.echo("❌ No project.yaml found. Run `biotope init <name>` first.")
        raise click.Abort

    project = Project.load(project_path)

    if show:
        click.echo(project.model_dump_json(indent=2))
        return

    if edit:
        editor = os.environ.get("EDITOR", "vi")
        subprocess.run([editor, str(project_path)], check=False)
        Project.load(project_path)  # re-validate
        console.print(f"✅ Saved {project_path}")
        return

    data = project.model_dump()
    if purpose is not None:
        data["purpose"] = purpose
    if notes is not None:
        data["notes"] = notes
    if clear_entities:
        data["required_entities"] = []
    if entities:
        data["required_entities"] = list(data["required_entities"]) + list(entities)
    if clear_relations:
        data["required_relations"] = []
    if relations:
        data["required_relations"] = list(data["required_relations"]) + list(relations)
    if clear_sources:
        data["data_sources"] = []
    if sources:
        data["data_sources"] = list(data["data_sources"]) + list(sources)

    updated = Project.model_validate(data)
    updated.dump(project_path)
    console.print(f"✅ Updated [cyan]{project_path}[/cyan]")
    console.print(f"   purpose: [dim]{updated.purpose or '(empty)'}[/dim]")
    console.print(f"   entities: {', '.join(updated.required_entities) or '(none)'}")
    console.print(f"   relations: {', '.join(updated.required_relations) or '(none)'}")
