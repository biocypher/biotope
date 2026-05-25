"""Push command implementation using Git under the hood."""

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
    "--force",
    "-f",
    is_flag=True,
    help="Force push (use with caution)",
)
def push(remote: str, branch: Optional[str], force: bool) -> None:
    """
    Push metadata changes to remote repository using Git.

    Pushes committed changes in .biotope/ directory to the remote repository.
    Similar to git push but focused on metadata.

    Args:
        remote: Remote repository name
        branch: Branch name to push
        force: Force push (use with caution)
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

    # Push changes
    if _push_changes(biotope_root, remote, branch, force):
        click.echo(f"✅ Successfully pushed metadata to {remote}/{branch}")
    else:
        click.echo("❌ Failed to push metadata changes.")


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


def _push_changes(biotope_root: Path, remote: str, branch: str, force: bool) -> bool:
    """Push changes to remote repository."""
    try:
        # Build push command
        cmd = ["git", "push"]

        if force:
            cmd.append("--force")

        cmd.extend([remote, branch])

        # Execute push
        subprocess.run(cmd, cwd=biotope_root, capture_output=True, text=True, check=True)

        return True

    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Git push failed: {e}")
        if e.stderr:
            click.echo(f"Error details: {e.stderr}")
        return False
