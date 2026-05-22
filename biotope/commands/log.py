"""Log command implementation using Git under the hood."""

import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.console import Console

from biotope.utils import find_biotope_root, is_git_repo


@click.command()
@click.option(
    "--oneline",
    is_flag=True,
    help="Show one line per commit",
)
@click.option(
    "--max-count",
    "-n",
    type=int,
    help="Limit the number of commits to output",
)
@click.option(
    "--since",
    help="Show commits more recent than a specific date",
)
@click.option(
    "--author",
    help="Show commits by specific author",
)
@click.option(
    "--biotope-only",
    is_flag=True,
    help="Show only commits affecting .biotope/ directory",
)
def log(
    oneline: bool, max_count: Optional[int], since: Optional[str], author: Optional[str], biotope_only: bool
) -> None:
    """Show commit history using Git."""
    console = Console()

    # Find biotope project root
    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    # Check if we're in a Git repository
    if not is_git_repo(biotope_root):
        click.echo("❌ Not in a Git repository. Initialize Git first with 'git init'.")
        raise click.Abort

    # Get Git log
    commits = _get_git_log(biotope_root, max_count, since, author, biotope_only)

    if not commits:
        click.echo("No commits found.")
        return

    if oneline:
        _show_oneline_log(commits, console)
    else:
        _show_detailed_log(commits, console)


def _show_oneline_log(commits: List[Dict], console: Console) -> None:
    """Show commits in one-line format."""
    for commit in commits:
        console.print(f"{commit['hash'][:8]} {commit['date']} {commit['author']}: {commit['message']}")


def _show_detailed_log(commits: List[Dict], console: Console) -> None:
    """Show commits in detailed format."""
    for i, commit in enumerate(commits):
        if i > 0:
            console.print()

        # Commit header
        console.print(f"[bold blue]commit {commit['hash']}[/]")
        console.print(f"[dim]Author: {commit['author']}[/]")
        console.print(f"[dim]Date: {commit['date']}[/]")
        console.print()
        console.print(f"    {commit['message']}")

        # Files changed (if available)
        if commit.get("files"):
            console.print()
            console.print("[dim]Files:[/]")
            for file_path in commit["files"]:
                console.print(f"    {file_path}")


def _get_git_log(
    biotope_root: Path,
    max_count: Optional[int] = None,
    since: Optional[str] = None,
    author: Optional[str] = None,
    biotope_only: bool = False,
) -> List[Dict]:
    """Get Git log with optional filtering."""
    try:
        # Build git log command
        cmd = ["git", "log", "--pretty=format:%H|%an|%ad|%s", "--date=short"]

        if max_count:
            cmd.extend(["-n", str(max_count)])

        if since:
            cmd.extend(["--since", since])

        if author:
            cmd.extend(["--author", author])

        if biotope_only:
            cmd.append("--")
            cmd.append(".biotope/")

        # Execute git log
        result = subprocess.run(cmd, cwd=biotope_root, capture_output=True, text=True, check=True)

        commits = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue

            # Parse commit line: hash|author|date|message
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commit_hash, author_name, date, message = parts
                commits.append(
                    {
                        "hash": commit_hash,
                        "author": author_name,
                        "date": date,
                        "message": message,
                        "files": _get_commit_files(biotope_root, commit_hash, biotope_only),
                    }
                )

        return commits

    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Git error: {e}")
        return []


def _get_commit_files(biotope_root: Path, commit_hash: str, biotope_only: bool) -> List[str]:
    """Get files changed in a specific commit."""
    try:
        cmd = ["git", "show", "--name-only", "--pretty=format:", commit_hash]

        if biotope_only:
            cmd.append("--")
            cmd.append(".biotope/")

        result = subprocess.run(cmd, cwd=biotope_root, capture_output=True, text=True, check=True)

        files = []
        for line in result.stdout.splitlines():
            if line.strip() and not line.startswith("commit"):
                files.append(line.strip())

        return files

    except subprocess.CalledProcessError:
        return []
