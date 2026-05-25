"""Pull command implementation using Git under the hood."""

import subprocess
from pathlib import Path
from typing import Optional

import click

from biotope.utils import find_biotope_root, is_git_repo


@click.command()
@click.option(
    "--remote",
    "-r",
    help="Remote repository name (default: origin)",
    default="origin",
)
@click.option(
    "--branch",
    "-b",
    help="Branch name (default: current branch)",
)
@click.option(
    "--rebase",
    is_flag=True,
    help="Use rebase instead of merge",
)
def pull(remote: str, branch: Optional[str], rebase: bool) -> None:
    """
    Pull metadata changes from remote repository using Git.

    Pulls committed changes in .biotope/ directory from the remote repository.
    Similar to git pull but focused on metadata.

    Args:
        remote: Remote repository name
        branch: Branch name to pull
        rebase: Use rebase instead of merge
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

    # Check if remote exists
    if not _remote_exists(biotope_root, remote):
        click.echo(f"❌ Remote '{remote}' not found. Add it with 'git remote add {remote} <url>'.")
        raise click.Abort

    # Get current branch if not specified
    if not branch:
        branch = _get_current_branch(biotope_root)
        if not branch:
            click.echo("❌ Could not determine current branch.")
            raise click.Abort

    # Pull changes
    if _pull_changes(biotope_root, remote, branch, rebase):
        click.echo(f"✅ Successfully pulled metadata from {remote}/{branch}")
    else:
        click.echo("❌ Failed to pull metadata changes.")


def _remote_exists(biotope_root: Path, remote: str) -> bool:
    """Check if remote exists."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", remote], cwd=biotope_root, capture_output=True, text=True, check=True
        )
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def _get_current_branch(biotope_root: Path) -> Optional[str]:
    """Get current branch name."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"], cwd=biotope_root, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _pull_changes(biotope_root: Path, remote: str, branch: str, rebase: bool) -> bool:
    """Pull changes from remote repository."""
    try:
        # Build pull command
        cmd = ["git", "pull"]

        if rebase:
            cmd.append("--rebase")

        cmd.extend([remote, branch])

        # Execute pull
        subprocess.run(cmd, cwd=biotope_root, capture_output=True, text=True, check=True)

        return True

    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Git pull failed: {e}")
        if e.stderr:
            click.echo(f"Error details: {e.stderr}")
        return False
