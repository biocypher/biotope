"""Command for downloading files and integrating with biotope workflow."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import click
import requests
from rich.progress import Progress, SpinnerColumn, TextColumn

from biotope.commands.add import _add_file
from biotope.utils import find_biotope_root, is_git_repo, stage_git_changes


def download_file(url: str, output_dir: Path) -> Path | None:
    """Download a file from URL with progress bar."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Get filename from URL or Content-Disposition header
        filename = None
        if "Content-Disposition" in response.headers:
            content_disposition = response.headers["Content-Disposition"]
            if "filename=" in content_disposition:
                filename = content_disposition.split("filename=")[1].strip('"')

        if not filename:
            filename = Path(urlparse(url).path).name
            if not filename or filename == "":
                filename = "downloaded_file"

        output_path = output_dir / filename

        total_size = int(response.headers.get("content-length", 0))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(f"Downloading {filename}...", total=total_size)

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))

        return output_path
    except Exception as e:
        click.echo(f"Error downloading file: {e}", err=True)
        return None


def _call_biotope_add(file_path: Path, biotope_root: Path) -> bool:
    """Add downloaded file to biotope project."""
    try:
        # Create datasets directory
        datasets_dir = biotope_root / ".biotope" / "datasets"
        datasets_dir.mkdir(parents=True, exist_ok=True)

        # Add the file using the same logic as the add command
        success = _add_file(file_path, biotope_root, datasets_dir, force=False)

        if success:
            # Stage changes in Git
            stage_git_changes(biotope_root)

        return success

    except FileNotFoundError:
        click.echo(f"❌ File not found: {file_path}", err=True)
        return False
    except PermissionError:
        click.echo(f"❌ Permission denied accessing: {file_path}", err=True)
        return False
    except Exception as e:
        click.echo(f"❌ Failed to add file to biotope project: {e}", err=True)
        return False


@click.command()
@click.argument("url")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(file_okay=False),
    default="data/raw",
    help="Directory to save downloaded files",
)
@click.option(
    "--no-add",
    is_flag=True,
    help="Download file without adding to biotope project",
)
def get(url: str, output_dir: str, no_add: bool) -> None:
    """
    Download a file and integrate with biotope workflow.

    Downloads a file from the given URL and automatically adds it to the biotope project
    for staging and annotation. The file will be visible in 'biotope status' and can be
    annotated using 'biotope annotate --staged'.

    URL can be any valid HTTP/HTTPS URL pointing to a file.
    """
    # Find biotope project root
    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    # Check if we're in a Git repository
    if not is_git_repo(biotope_root):
        click.echo("❌ Not in a Git repository. Initialize Git first with 'git init'.")
        raise click.Abort

    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Download the file
    click.echo(f"📥 Downloading file from: {url}")
    downloaded_file = download_file(url, output_path)

    if not downloaded_file:
        click.echo("❌ Failed to download file")
        raise click.Abort

    click.echo(f"✅ Downloaded: {downloaded_file}")

    # Add to biotope project unless --no-add flag is used
    if not no_add:
        click.echo(f"📁 Adding file to biotope project...")
        if _call_biotope_add(downloaded_file, biotope_root):
            click.echo(f"✅ File added to biotope project")
            click.echo(f"\n💡 Next steps:")
            click.echo(f"  1. Run 'biotope status' to see staged files")
            click.echo(f"  2. Run 'biotope annotate --staged' to create metadata")
            click.echo(f"  3. Run 'biotope commit -m \"message\"' to save changes")
        else:
            click.echo(f"⚠️  File downloaded but not added to biotope project")
            click.echo(
                f"   You can manually add it with: biotope add {downloaded_file}"
            )
    else:
        click.echo(f"\n💡 File downloaded. To add to biotope project:")
        click.echo(f"  biotope add {downloaded_file}")
