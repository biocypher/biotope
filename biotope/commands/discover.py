"""``biotope discover`` — rank registered adapters and local Croissant files."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console

from biotope.croissant.api import discover_sources, propose_decomposition
from biotope.project_model import find_project


console = Console()


@click.command()
@click.option(
    "--project",
    "project_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to project.yaml. Default: auto-detect from cwd.",
)
@click.option(
    "--registry",
    "registries",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Local registry directory. Repeatable.",
)
@click.option("--http-registry", type=str, default=None, help="HTTP registry base URL.")
@click.option(
    "--baker-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Directory of locally-baked Croissant files to include in discovery.",
)
def discover(
    project_path: Path | None,
    registries: tuple[Path, ...],
    http_registry: str | None,
    baker_dir: Path | None,
) -> None:
    """Find adapters and Croissant files that match the project's required entities."""
    if project_path is None:
        project_path = find_project()
        if project_path is None:
            click.echo("❌ No project.yaml found. Pass --project or run `biotope init` first.")
            raise click.Abort

    decomposition = propose_decomposition(project_path)
    if not decomposition["required_entities"]:
        console.print(
            "[yellow]⚠️  project.yaml has no required_entities — nothing to match.[/yellow]\n"
            "Run [bold]biotope describe --entity gene --entity disease[/bold] first.",
        )

    result = discover_sources(
        decomposition,
        registry_paths=list(registries) or None,
        local_baker_dir=baker_dir,
        http_registry_url=http_registry,
    )
    click.echo(json.dumps(result, indent=2, default=str))
