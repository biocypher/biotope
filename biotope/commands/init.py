"""Initialize command implementation."""

from datetime import datetime, timezone
from pathlib import Path

import click
import yaml
from rich.console import Console

from biotope.utils import is_git_repo


@click.command()
@click.option(
    "--dir",
    "-d",
    type=click.Path(file_okay=False, path_type=Path),
    default=".",
    help="Directory to initialize biotope project in",
)
def init(dir: Path) -> None:  # noqa: A002
    """
    Initialize a new biotope with interactive configuration in the specified directory.
    """
    # Check if .biotope directory already exists
    biotope_dir = dir / ".biotope"
    if biotope_dir.exists():
        click.echo("❌ A biotope project already exists in this directory.")
        click.echo("To start fresh, remove the .biotope directory first.")
        raise click.Abort

    click.echo("Establishing biotope! Let's set up your project.\n")

    # Project name
    project_name = click.prompt(
        "What's your project name?",
        type=str,
        default=dir.absolute().name,
    )

    # Knowledge sources
    knowledge_sources = []
    use_knowledge_graph = click.confirm(
        "Would you like to install a knowledge graph now?", default=False
    )
    if use_knowledge_graph:
        while True:
            source = click.prompt(
                "\nEnter knowledge source or press enter to finish.",
                type=str,
                default="",
                show_default=False,
            )
            if not source:
                break
            source_type = click.prompt(
                "What type of source is this?",
                type=click.Choice(["database", "file", "api"], case_sensitive=False),
                default="database",
            )
            knowledge_sources.append({"name": source, "type": source_type})

    # Output preferences - only ask if knowledge graph is being used
    output_format = "neo4j"  # Default
    if use_knowledge_graph:
        output_format = click.prompt(
            "\nPreferred output format",
            type=click.Choice(["neo4j", "csv", "json"], case_sensitive=False),
            default="neo4j",
        )

    # LLM integration
    use_llm = click.confirm(
        "\nWould you like to set up LLM integration?", default=False
    )
    if use_llm:
        llm_provider = click.prompt(
            "Which LLM provider would you like to use?",
            type=click.Choice(
                ["google", "openai", "anthropic", "local"], case_sensitive=False
            ),
            default="openai",
        )

        if llm_provider in ["google", "openai", "anthropic"]:
            api_key = click.prompt(
                f"Please enter your {llm_provider} API key",
                type=str,
                hide_input=True,
            )

    # Project-level metadata collection for pre-filling annotations
    console = Console()
    console.print("\n[bold blue]Project Metadata Setup[/]")
    console.print(
        "The following information will be used to pre-fill metadata forms when creating dataset annotations."
    )
    console.print("You can skip any fields and provide them later during annotation.")

    collect_project_metadata = click.confirm(
        "\nWould you like to set up project-level metadata now? This will be used to pre-fill metadata later.",
        default=True,
    )

    project_metadata = {}
    if collect_project_metadata:
        console.print("\n[bold green]Project Information[/]")
        console.print("─" * 50)

        # Project description
        project_description = click.prompt(
            "Project description (what is this project about?)",
            default="",
            show_default=False,
        )
        if project_description:
            project_metadata["description"] = project_description

        # Project URL
        project_url = click.prompt(
            "Project URL (if available)",
            default="",
            show_default=False,
        )
        if project_url:
            project_metadata["url"] = project_url

        # Creator/Contact
        creator = click.prompt(
            "Primary contact person (email preferred)",
            default="",
            show_default=False,
        )
        if creator:
            project_metadata["creator"] = creator

        # License
        license_url = click.prompt(
            "Default license URL",
            default="https://creativecommons.org/licenses/by/4.0/",
            show_default=True,
        )
        if license_url:
            project_metadata["license"] = license_url

        # Citation template
        citation_template = click.prompt(
            "Citation template (use {name} and {year} as placeholders)",
            default="Please cite this dataset as: {name} ({year})",
            show_default=True,
        )
        if citation_template:
            project_metadata["citation"] = citation_template

        # Access restrictions
        has_access_restrictions = click.confirm(
            "Does this project have default access restrictions?",
            default=False,
        )
        if has_access_restrictions:
            access_restrictions = click.prompt(
                "Default access restrictions description",
                default="",
                show_default=False,
            )
            if access_restrictions:
                project_metadata["access_restrictions"] = access_restrictions

        # Legal obligations
        has_legal_obligations = click.confirm(
            "Does this project have default legal obligations?",
            default=False,
        )
        if has_legal_obligations:
            legal_obligations = click.prompt(
                "Default legal obligations description",
                default="",
                show_default=False,
            )
            if legal_obligations:
                project_metadata["legal_obligations"] = legal_obligations

        # Collaboration partner
        has_collaboration_partner = click.confirm(
            "Does this project have a collaboration partner?",
            default=False,
        )
        if has_collaboration_partner:
            collaboration_partner = click.prompt(
                "Collaboration partner and institute",
                default="",
                show_default=False,
            )
            if collaboration_partner:
                project_metadata["collaboration_partner"] = collaboration_partner

        # Store project name for consistency
        project_metadata["project_name"] = project_name

    # Create user configuration
    user_config = {
        "project": {
            "name": project_name,
            "output_format": output_format,
        },
        "knowledge_sources": knowledge_sources,
    }

    if use_llm:
        user_config["llm"] = {
            "provider": llm_provider,
            "api_key": api_key if llm_provider in ["openai", "anthropic"] else None,
        }

    # Create internal metadata
    metadata = {
        "project_name": project_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "biotope_version": click.get_current_context().obj.get("version", "unknown"),
        "last_modified": datetime.now(timezone.utc).isoformat(),
        "builds": [],
        "knowledge_sources": knowledge_sources,
    }

    # Create project structure
    try:
        # Initialize Git if not already initialized
        git_was_initialized = False
        if not is_git_repo(dir):
            if click.confirm(
                "\nDo you confirm to initialize Git for version control? (It is necessary to use biotope.)",
                default=True,
            ):
                _init_git_repo(dir)
                git_was_initialized = True
                click.echo("✅ Git repository initialized")
            else:
                click.echo("❌ Git is necessary to use biotope")
                raise click.Abort

        dir.mkdir(parents=True, exist_ok=True)
        create_project_structure(dir, user_config, metadata, project_metadata)
        
        # Create initial commit with project files if Git was just initialized
        if git_was_initialized:
            _create_initial_commit(dir)

        click.echo("\n✨ Biotope established successfully! ✨")
        click.echo(
            f"\nYour biotope '{project_name}' has been established. Make sure to water regularly.",
        )
        click.echo("\nNext steps:")
        click.echo("1. Review the configuration in config/biotope.yaml")
        if use_knowledge_graph:
            click.echo("2. Add your knowledge sources")
        click.echo("3. Run 'biotope add <file>' to stage data files")
        click.echo("4. Run 'biotope annotate interactive --staged' to create metadata")
        click.echo("5. Run 'biotope commit -m \"message\"' to save changes")

        if collect_project_metadata and project_metadata:
            click.echo(
                "\n💡 Project metadata has been saved and will be used to pre-fill annotation forms."
            )
            click.echo(
                "   You can update it later with 'biotope config set-project-metadata'"
            )
    except (OSError, yaml.YAMLError) as e:
        click.echo(f"\n❌ Error initializing project: {e!s}", err=True)
        raise click.Abort from e


def create_project_structure(
    directory: Path, config: dict, metadata: dict, project_metadata: dict = None
) -> None:
    """
    Create the project directory structure and configuration files.

    Args:
        directory: Project directory path
        config: User-facing configuration dictionary
        metadata: Internal metadata dictionary (now consolidated into biotope config)
        project_metadata: Project-level metadata for pre-filling annotations

    """
    # Create directory structure - git-on-top layout
    dirs = [
        ".biotope",
        ".biotope/config",  # Configuration for biotope project
        ".biotope/datasets",  # Stores Croissant ML JSON-LD files
        ".biotope/workflows",  # Bioinformatics workflow definitions
        ".biotope/logs",  # Command execution logs
        "config",
        "data",
        "data/raw",
        "data/processed",
        "schemas",
        "outputs",
    ]

    for d in dirs:
        (directory / d).mkdir(parents=True, exist_ok=True)

    # Create user-facing config file
    (directory / "config" / "biotope.yaml").write_text(
        yaml.dump(config, default_flow_style=False),
    )

    # Create consolidated biotope config (Git-like approach)
    biotope_config = {
        "version": "1.0",
        "croissant_schema_version": "1.0",
        "default_metadata_template": "scientific",
        "data_storage": {"type": "local", "path": "data"},
        "checksum_algorithm": "sha256",
        "auto_stage": True,
        "commit_message_template": "Update metadata: {description}",
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
        # Consolidate internal metadata into config (Git-like approach)
        "project_info": {
            "name": metadata.get("project_name"),
            "created_at": metadata.get("created_at"),
            "biotope_version": metadata.get("biotope_version"),
            "last_modified": metadata.get("last_modified"),
            "builds": metadata.get("builds", []),
            "knowledge_sources": metadata.get("knowledge_sources", []),
        },
    }

    # Add project metadata if provided
    if project_metadata:
        biotope_config["project_metadata"] = project_metadata

    (directory / ".biotope" / "config" / "biotope.yaml").write_text(
        yaml.dump(biotope_config, default_flow_style=False),
    )

    # Create .gitignore file to exclude data files and other common files
    gitignore_content = """# Biotope data files (not tracked in Git)
# Data files are tracked through metadata in .biotope/datasets/
/data/
/downloads/
/tmp/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Jupyter
.ipynb_checkpoints
*/.ipynb_checkpoints/*

# Logs
*.log
logs/

# Temporary files
*.tmp
*.temp
"""
    (directory / ".gitignore").write_text(gitignore_content)

    # Note: No custom refs needed - Git handles all version control

    # Create README
    readme_content = f"""# {config["project"]["name"]}

A BioCypher knowledge graph project managed with biotope.

## Project Structure

- `config/`: User configuration files
- `data/`: Data files (not tracked in Git)
  - `raw/`: Raw input data
  - `processed/`: Processed data
- `schemas/`: Knowledge schema definitions
- `outputs/`: Generated knowledge graphs
- `.biotope/`: Biotope project management (Git-tracked)
  - `datasets/`: Croissant ML metadata files
  - `workflows/`: Bioinformatics workflow definitions
  - `config/`: Biotope configuration (Git-like approach)
  - `logs/`: Command execution history

## Git Integration

This project uses Git for metadata version control. The `.biotope/` directory is tracked by Git, allowing you to:
- Version control your metadata changes
- Collaborate with others on metadata
- Use standard Git tools and workflows

**Note**: Data files in the `data/` directory are intentionally excluded from Git tracking via `.gitignore`. This is because:
- Data files are often large and would bloat the repository
- Data files are tracked through metadata in `.biotope/datasets/`
- Checksums ensure data integrity without storing the actual files

## Getting Started

1. Add data files: `biotope add <data_file>`
2. Create metadata: `biotope annotate interactive --staged`
3. Check status: `biotope status`
4. Commit changes: `biotope commit -m "Add new dataset"`
5. View history: `biotope log`
6. Push/pull: `biotope push` / `biotope pull`

## Standard Git Commands

You can also use standard Git commands:
- `git status` - See all project changes
- `git log -- .biotope/` - View metadata history
- `git diff .biotope/` - See metadata changes
"""
    (directory / "README.md").write_text(readme_content)


def _init_git_repo(directory: Path) -> None:
    """Initialize a Git repository in the directory."""
    try:
        import subprocess

        subprocess.run(["git", "init"], cwd=directory, check=True)

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        click.echo(f"⚠️  Warning: Could not initialize Git: {e}")


def _create_initial_commit(directory: Path) -> None:
    """Create initial commit with project files."""
    try:
        import subprocess

        # Add all files and create initial commit
        subprocess.run(["git", "add", "."], cwd=directory, check=True)

        subprocess.run(
            ["git", "commit", "-m", "Initial biotope project setup"],
            cwd=directory,
            check=True,
        )

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        click.echo(f"⚠️  Warning: Could not create initial commit: {e}")
