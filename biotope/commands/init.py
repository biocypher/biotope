"""``biotope init`` — scaffold a new biotope project.

Default behavior is **pure scaffold**: create the directory layout, drop an
``AGENTS.md`` for the agent surface, write an empty ``project.yaml``, run
``git init``. No content questions. The agent (or the user via
``biotope describe``) fills in the competence questions afterwards.

Use ``--interactive`` to open ``$EDITOR`` on the freshly-written
``project.yaml`` so the user can fill ``purpose:`` before exiting init.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console

from biotope.project_model import Project, resolve_project_path

PURPOSE_PROMPT = (
    "What is the main purpose or aim of this project?\n"
    "  (one or two sentences; press Enter to skip and set later via "
    "`biotope describe --purpose ...`)"
)

console = Console()

TEMPLATES = Path(__file__).parent.parent / "templates"

DEFAULT_BIOTOPE_CONFIG: dict = {
    "version": "0.1",
    "croissant_schema_version": "1.1",
    "data_storage": ".biotope/datasets",
    "annotation_validation": {
        "enabled": True,
        "minimum_required_fields": [
            "name",
            "description",
            "creator",
            "dateCreated",
            "distribution",
        ],
        "field_validation": {
            "name": {"type": "string", "min_length": 1},
            "description": {"type": "string", "min_length": 10},
            "creator": {"type": "object", "required_keys": ["name"]},
            "dateCreated": {"type": "string", "format": "date"},
            "distribution": {"type": "array", "min_length": 1},
        },
    },
}


@click.command()
@click.argument("name", required=False)
@click.option(
    "--dir",
    "-d",
    type=click.Path(file_okay=False, path_type=Path),
    default=".",
    help="Parent directory to initialise the project in. The project goes in NAME/ within this dir.",
)
@click.option(
    "--purpose",
    "-p",
    type=str,
    default=None,
    help=(
        "Seed the project's purpose directly. "
        "If omitted and stdin is a TTY, init will prompt; pass --no-prompt to skip."
    ),
)
@click.option(
    "--no-prompt",
    is_flag=True,
    default=False,
    help="Never prompt interactively. Combined with no --purpose, leaves it empty.",
)
@click.option(
    "--no-git",
    is_flag=True,
    default=False,
    help="Skip running `git init`. The .biotope/ directory is still created.",
)
@click.option(
    "--visible",
    is_flag=True,
    default=False,
    help="Write project.yaml at the project root instead of inside .biotope/.",
)
@click.option(
    "--interactive",
    is_flag=True,
    default=False,
    help="Open $EDITOR on project.yaml so you can fill in purpose before exiting init.",
)
def init(
    name: str | None,
    dir: Path,  # noqa: A002
    purpose: str | None,
    no_prompt: bool,
    no_git: bool,
    visible: bool,
    interactive: bool,
) -> None:
    """Scaffold a new biotope project.

    Default invocation: ``biotope init my-project``. Creates ``my-project/`` with
    ``.biotope/``, ``data/``, ``mappings/``, an ``AGENTS.md`` for agents to read,
    and an empty ``project.yaml``. Runs ``git init`` unless ``--no-git`` is set.
    """
    if name is None:
        name = click.prompt("Project name", type=str)

    if purpose is None:
        if no_prompt or not sys.stdin.isatty():
            purpose = ""
        else:
            click.echo(PURPOSE_PROMPT)
            purpose = click.prompt("purpose", default="", show_default=False)

    project_dir = (dir / name).resolve() if name != "." else dir.resolve()
    if name == ".":
        name = project_dir.name

    if (project_dir / ".biotope").exists():
        click.echo(f"❌ {project_dir} already contains a .biotope/ directory.")
        raise click.Abort

    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".biotope" / "datasets").mkdir(parents=True, exist_ok=True)
    (project_dir / ".biotope" / "workflows").mkdir(parents=True, exist_ok=True)
    (project_dir / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (project_dir / "data" / "processed").mkdir(parents=True, exist_ok=True)
    (project_dir / "mappings").mkdir(exist_ok=True)

    config_path = project_dir / ".biotope" / "config.yaml"
    config_path.write_text(yaml.safe_dump(DEFAULT_BIOTOPE_CONFIG, sort_keys=False))

    project = Project(name=name, purpose=purpose)
    project_yaml_path = resolve_project_path(project_dir, visible=visible)
    project_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    project.dump(project_yaml_path)

    agents_md_dest = project_dir / "AGENTS.md"
    agents_md_src = TEMPLATES / "AGENTS.md"
    shutil.copy(agents_md_src, agents_md_dest)

    gitignore = project_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("data/raw/\ndata/processed/\n__pycache__/\n*.pyc\n.venv/\n")

    if not no_git:
        try:
            subprocess.run(["git", "init", "-q"], cwd=project_dir, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            click.echo(f"⚠️  git init failed: {exc}")

    if interactive:
        editor = os.environ.get("EDITOR", "vi")
        try:
            subprocess.run([editor, str(project_yaml_path)], check=True)
            Project.load(project_yaml_path)  # validate after edit
        except subprocess.CalledProcessError:
            click.echo(f"⚠️  Editor exited non-zero; {project_yaml_path} may be empty.")

    console.print(f"✅ Initialised biotope project at [cyan]{project_dir}[/cyan]")
    console.print(f"   project.yaml: [dim]{project_yaml_path.relative_to(project_dir)}[/dim]")
    if purpose:
        console.print(f"   purpose: [dim]{purpose}[/dim]")
        console.print(
            "   Next: add entities and relations with "
            "[bold]biotope describe --entity ... --relation ...[/bold].",
        )
    else:
        console.print(
            "   Next: set purpose with [bold]biotope describe --purpose \"...\"[/bold].",
        )
