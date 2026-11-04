from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import click
import yaml
from rich.console import Console
from rich.table import Table

from biotope.utils import find_biotope_root


@click.group()
def config() -> None:
    """Manage biotope project configuration."""


@config.command()
def show_project_metadata() -> None:
    """Show current project-level metadata configuration."""
    console = Console()

    # Find biotope project root
    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    # Load config
    config = _read_config(biotope_root)
    project_metadata = config.get("project_metadata", {})

    if project_metadata:
        console.print("\n[bold blue]Project Metadata Configuration[/]")
        console.print("This metadata will be used to pre-fill annotation forms:")

        table = Table(show_header=False)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        for key, value in project_metadata.items():
            if key == "creator" and isinstance(value, dict):
                display_value = value.get("name", str(value))
            else:
                display_value = str(value)
            table.add_row(key, display_value)

        console.print(table)
        console.print("\n💡 Use 'biotope config set-project-metadata' to update these values")
    else:
        console.print("\n[bold yellow]No project metadata configured[/]")
        console.print("Use 'biotope config set-project-metadata' to add project-level metadata")


@config.command()
def set_project_metadata() -> None:
    """Set project-level metadata for pre-filling annotations."""
    console = Console()

    # Find biotope project root
    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    config_path = biotope_root / ".biotope" / "config.yaml"
    if not config_path.exists():
        click.echo("❌ Biotope configuration not found. Run 'biotope init' first.")
        raise click.Abort

    # Load current config
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        click.echo(f"❌ Error reading configuration: {e}")
        raise click.Abort

    # Initialize project_metadata if it doesn't exist
    if "project_metadata" not in config:
        config["project_metadata"] = {}

    current_metadata = config["project_metadata"]

    console.print("\n[bold blue]Project Metadata Setup[/]")
    console.print(
        "The following information will be used to pre-fill metadata forms when creating dataset annotations."
    )
    console.print("You can skip any fields by pressing Enter.")
    console.print()

    # Project description
    project_description = click.prompt(
        "Project description (what is this project about?)",
        default=current_metadata.get("description", ""),
        show_default=True,
    )
    if project_description:
        current_metadata["description"] = project_description
    elif "description" in current_metadata:
        del current_metadata["description"]

    # Project URL
    project_url = click.prompt(
        "Project URL (if available)",
        default=current_metadata.get("url", ""),
        show_default=True,
    )
    if project_url:
        current_metadata["url"] = project_url
    elif "url" in current_metadata:
        del current_metadata["url"]

    # Creator/Contact
    creator = click.prompt(
        "Primary contact person (email preferred)",
        default=current_metadata.get("creator", ""),
        show_default=True,
    )
    if creator:
        current_metadata["creator"] = creator
    elif "creator" in current_metadata:
        del current_metadata["creator"]

    # License
    license_url = click.prompt(
        "Default license URL",
        default=current_metadata.get("license", ""),
        show_default=True,
    )
    if license_url:
        current_metadata["license"] = license_url
    elif "license" in current_metadata:
        del current_metadata["license"]

    # Citation template
    citation_template = click.prompt(
        "Citation template (use {name} and {year} as placeholders)",
        default=current_metadata.get("citation", "Please cite this dataset as: {name} ({year})"),
        show_default=True,
    )
    if citation_template:
        current_metadata["citation"] = citation_template
    elif "citation" in current_metadata:
        del current_metadata["citation"]

    # Access restrictions
    has_access_restrictions = click.confirm(
        "Does this project have default access restrictions?",
        default=bool(current_metadata.get("access_restrictions")),
    )
    if has_access_restrictions:
        access_restrictions = click.prompt(
            "Default access restrictions description",
            default=current_metadata.get("access_restrictions", ""),
            show_default=True,
        )
        if access_restrictions:
            current_metadata["access_restrictions"] = access_restrictions
        elif "access_restrictions" in current_metadata:
            del current_metadata["access_restrictions"]
    elif "access_restrictions" in current_metadata:
        del current_metadata["access_restrictions"]

    # Legal obligations
    has_legal_obligations = click.confirm(
        "Does this project have default legal obligations?",
        default=bool(current_metadata.get("legal_obligations")),
    )
    if has_legal_obligations:
        legal_obligations = click.prompt(
            "Default legal obligations description",
            default=current_metadata.get("legal_obligations", ""),
            show_default=True,
        )
        if legal_obligations:
            current_metadata["legal_obligations"] = legal_obligations
        elif "legal_obligations" in current_metadata:
            del current_metadata["legal_obligations"]
    elif "legal_obligations" in current_metadata:
        del current_metadata["legal_obligations"]

    # Collaboration partner
    has_collaboration_partner = click.confirm(
        "Does this project have a collaboration partner?",
        default=bool(current_metadata.get("collaboration_partner")),
    )
    if has_collaboration_partner:
        collaboration_partner = click.prompt(
            "Collaboration partner and institute",
            default=current_metadata.get("collaboration_partner", ""),
            show_default=True,
        )
        if collaboration_partner:
            current_metadata["collaboration_partner"] = collaboration_partner
        elif "collaboration_partner" in current_metadata:
            del current_metadata["collaboration_partner"]
    elif "collaboration_partner" in current_metadata:
        del current_metadata["collaboration_partner"]

    # Update config
    config["project_metadata"] = current_metadata

    # Save updated config
    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        if current_metadata:
            console.print("\n✅ Project metadata updated successfully")
            console.print("💡 This metadata will be used to pre-fill annotation forms")
        else:
            console.print("\n✅ Project metadata cleared")
            console.print("💡 No default values will be used for annotations")

    except yaml.YAMLError as e:
        click.echo(f"❌ Error writing configuration: {e}")
        raise click.Abort


def _read_config(root: Path) -> dict[str, Any]:
    path = root / ".biotope" / "config.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    return cast(dict[str, Any], loaded) if isinstance(loaded, dict) else {}
