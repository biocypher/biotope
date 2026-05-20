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
from rich.panel import Panel

from biotope.project_model import Project, find_project, resolve_project_path

console = Console()


def _render_state_and_hints(project_path: Path, project: Project) -> None:
    """Show the current project document plus a reminder of mutating flags."""
    lines = [
        f"[bold]name:[/bold] {project.name}",
        f"[bold]purpose:[/bold] {project.purpose or '[dim](not set)[/dim]'}",
        f"[bold]required entities:[/bold] {', '.join(project.required_entities) or '[dim](none)[/dim]'}",
        f"[bold]required relations:[/bold] {', '.join(project.required_relations) or '[dim](none)[/dim]'}",
    ]
    if project.data_sources:
        lines.append(f"[bold]data sources:[/bold] {', '.join(project.data_sources)}")
    if project.notes:
        lines.append(f"[bold]notes:[/bold] {project.notes}")
    console.print(
        Panel("\n".join(lines), title=str(project_path), border_style="cyan", expand=False),
    )
    console.print(
        "\n[bold]Update this document with flags[/bold] "
        "(repeat list flags as needed; free text accepted):\n"
        "  --purpose \"…\"               replace the project purpose\n"
        "  --entity \"…\"                add an entity (e.g. drug, gene, customer)\n"
        "  --relation \"…\"              add a relation (e.g. \"which drugs target which proteins\")\n"
        "  --source \"…\"                record a data source (path, URL, or registry id)\n"
        "  --notes \"…\"                 replace the free-form notes field\n"
        "  --clear-entities | --clear-relations | --clear-sources   reset the list before adding\n"
        "  --edit                        open $EDITOR on project.yaml instead\n"
        "  --show                        same as running `biotope describe` with no flags",
    )


@click.command()
@click.option("--purpose", "-p", type=str, default=None, help="Replace the project's purpose statement.")
@click.option(
    "--entity",
    "-e",
    "entities",
    multiple=True,
    help=(
        "Add to required_entities. Repeatable. Free text — usually a noun "
        "(e.g. 'drug', 'gene', 'customer', 'invoice line item'). "
        "Use --clear-entities to reset first."
    ),
)
@click.option(
    "--relation",
    "-r",
    "relations",
    multiple=True,
    help=(
        "Add to required_relations. Repeatable. Free text — can be a short "
        "label ('drug_targets_gene') or a natural-language statement "
        "('which drugs target which proteins')."
    ),
)
@click.option(
    "--source",
    "-s",
    "sources",
    multiple=True,
    help="Add to data_sources. Repeatable. A path, URL, or registry id.",
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

    no_mutation_requested = not any(
        [
            purpose is not None,
            notes is not None,
            entities,
            relations,
            sources,
            clear_entities,
            clear_relations,
            clear_sources,
            edit,
            show,
        ],
    )

    if show or no_mutation_requested:
        _render_state_and_hints(project_path, project)
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
