"""Status command implementation using Git under the hood."""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
from rich.console import Console
from rich.table import Table

from biotope.validation import (
    get_annotation_status_for_files,
    get_all_tracked_files,
    get_staged_metadata_files,
)
from biotope.utils import find_biotope_root, is_git_repo


@click.command()
@click.option(
    "--porcelain",
    is_flag=True,
    help="Output in machine-readable format",
)
@click.option(
    "--biotope-only",
    is_flag=True,
    help="Show only .biotope/ directory changes",
)
@click.option(
    "--detailed",
    is_flag=True,
    help="Show detailed validation errors for tracked datasets.",
)
def status(porcelain: bool, biotope_only: bool, detailed: bool) -> None:
    """
    Show the current status of the biotope project using Git.
    
    Displays Git status for .biotope/ directory changes.
    Similar to git status but focused on metadata.
    
    Args:
        porcelain: Output in machine-readable format
        biotope_only: Show only .biotope/ directory changes
        detailed: Show detailed validation errors for tracked datasets.
    """
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

    if porcelain:
        _show_porcelain_status(biotope_root, biotope_only)
    else:
        _show_rich_status(biotope_root, console, biotope_only, detailed)


def _show_rich_status(biotope_root: Path, console: Console, biotope_only: bool, detailed: bool) -> None:
    """Show status with rich formatting."""
    
    # Get Git status
    git_status = _get_git_status(biotope_root, biotope_only)
    
    console.print(f"\n[bold blue]Biotope Project Status[/]")
    console.print(f"Project: {biotope_root.name}")
    console.print(f"Location: {biotope_root}")
    console.print(f"Git Repository: {'✅' if is_git_repo(biotope_root) else '❌'}")
    
    # Get annotation status for staged files
    staged_metadata_files = get_staged_metadata_files(biotope_root)
    staged_annotation_status = get_annotation_status_for_files(biotope_root, staged_metadata_files)
    
    # Show changes with annotation status
    if git_status["staged"]:
        console.print(f"\n[bold green]Changes to be committed:[/]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Status", style="cyan")
        table.add_column("File", style="green")
        table.add_column("Annotated", style="yellow")
        
        for status, file_path in git_status["staged"]:
            # Check if this is a metadata file and get annotation status
            if file_path in staged_annotation_status:
                is_annotated, _ = staged_annotation_status[file_path]
                annotation_status = "✅" if is_annotated else "⚠️"
            else:
                annotation_status = "—"  # Not a metadata file
            
            table.add_row(status, file_path, annotation_status)
        console.print(table)
    
    if git_status["modified"]:
        console.print(f"\n[bold yellow]Changes not staged for commit:[/]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Status", style="cyan")
        table.add_column("File", style="green")
        
        for status, file_path in git_status["modified"]:
            table.add_row(status, file_path)
        console.print(table)
    
    if git_status["untracked"]:
        console.print(f"\n[bold red]Untracked files:[/]")
        for file_path in git_status["untracked"]:
            console.print(f"  ? {file_path}")
    
    # Show tracked files with annotation status
    tracked_metadata_files = get_all_tracked_files(biotope_root)
    tracked_annotation_status = {}
    has_incomplete_tracked = False
    if tracked_metadata_files:
        tracked_annotation_status = get_annotation_status_for_files(biotope_root, tracked_metadata_files)
        
        console.print(f"\n[bold blue]Tracked Datasets:[/]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Dataset", style="green")
        table.add_column("Annotated", style="yellow")
        table.add_column("Status", style="cyan")
        
        for file_path in tracked_metadata_files:
            dataset_name = Path(file_path).stem
            if file_path in tracked_annotation_status:
                is_annotated, errors = tracked_annotation_status[file_path]
                annotation_status = "✅" if is_annotated else "⚠️"
                status_text = "Complete" if is_annotated else f"Incomplete ({len(errors)} issues)"
            else:
                annotation_status = "❌"
                status_text = "Error reading metadata"
            
            table.add_row(dataset_name, annotation_status, status_text)
        console.print(table)
        
        has_incomplete_tracked = any(not is_annotated for is_annotated, _ in tracked_annotation_status.values())
        
        if detailed:
            files_with_errors = []
            for file_path, (is_annotated, errors) in tracked_annotation_status.items():
                if not is_annotated and errors:
                    files_with_errors.append((Path(file_path).stem, errors))

            if files_with_errors:
                console.print(f"\n[bold red]Validation Issues:[/]")
                for dataset_name, errors in files_with_errors:
                    console.print(f"  [bold yellow]{dataset_name}:[/]")
                    for error in errors:
                        console.print(f"    - {error}")
        elif has_incomplete_tracked:
            console.print(f"\n💡 Run 'biotope status --detailed' to see validation issues.")

    # Summary
    total_staged = len(git_status["staged"])
    total_modified = len(git_status["modified"])
    total_untracked = len(git_status["untracked"])
    
    # Count annotation status
    staged_annotated = sum(1 for is_annotated, _ in staged_annotation_status.values() if is_annotated)
    staged_unannotated = len(staged_annotation_status) - staged_annotated
    
    tracked_annotated = sum(1 for is_annotated, _ in tracked_annotation_status.values() if is_annotated)
    tracked_unannotated = len(tracked_annotation_status) - tracked_annotated
    
    console.print(f"\n[bold]Summary:[/]")
    console.print(f"  Staged: {total_staged} file(s) ({staged_annotated} annotated, {staged_unannotated} unannotated)")
    console.print(f"  Modified: {total_modified} file(s)")
    console.print(f"  Untracked: {total_untracked} file(s)")
    console.print(f"  Tracked datasets: {len(tracked_metadata_files)} ({tracked_annotated} annotated, {tracked_unannotated} unannotated)")
    
    # Check if there are staged metadata files that need annotation
    has_incomplete_annotations = any(not is_annotated for is_annotated, _ in staged_annotation_status.values())
    
    # Check if there are tracked metadata files that need annotation
    has_incomplete_tracked = any(not is_annotated for is_annotated, _ in tracked_annotation_status.values())

    show_next_steps = False
    if total_staged > 0 or total_modified > 0 or total_untracked > 0 or has_incomplete_tracked:
        console.print(f"\n💡 Next steps:")
        show_next_steps = True

    # Suggest annotate for staged files if needed
    if has_incomplete_annotations:
        console.print(f"  • Run 'biotope annotate interactive --staged' to complete metadata annotations for staged files")
    # Suggest annotate for incomplete tracked files if needed
    if has_incomplete_tracked:
        console.print(f"  • Run 'biotope annotate interactive --incomplete' to complete metadata annotations for all tracked files")
    # Suggest commit if there are staged files
    if total_staged > 0:
        console.print(f"  • Run 'biotope commit -m \"message\"' to commit changes")
    # Suggest add/annotate/commit if there are only modified or untracked files
    elif total_modified > 0 or total_untracked > 0:
        console.print(f"  • Run 'biotope add <data_file>' to add data files")
        console.print(f"  • Run 'biotope annotate interactive --staged' to create metadata")
        console.print(f"  • Run 'biotope commit -m \"message\"' to commit changes")


def _show_porcelain_status(biotope_root: Path, biotope_only: bool) -> None:
    """Show status in machine-readable format."""
    git_status = _get_git_status(biotope_root, biotope_only)
    
    for status, file_path in git_status["staged"]:
        click.echo(f"{status} {file_path}")
    
    for status, file_path in git_status["modified"]:
        click.echo(f"{status} {file_path}")
    
    for file_path in git_status["untracked"]:
        click.echo(f"?? {file_path}")


def _get_git_status(biotope_root: Path, biotope_only: bool) -> Dict[str, List]:
    """Get Git status for .biotope/ directory."""
    try:
        # Get Git status
        cmd = ["git", "status", "--porcelain"]
        if biotope_only:
            cmd.append(".biotope/")
        
        result = subprocess.run(
            cmd,
            cwd=biotope_root,
            capture_output=True,
            text=True,
            check=True
        )
        
        staged = []
        modified = []
        untracked = []
        
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            
            # Parse Git status line (e.g., "M  .biotope/datasets/file.jsonld")
            status = line[:2].strip()
            file_path = line[3:]
            
            if status == "??":
                untracked.append(file_path)
            elif status in ["A", "M", "D", "R"]:
                staged.append((status, file_path))
            elif status in [" M", " D", " R"]:
                modified.append((status.strip(), file_path))
        
        return {
            "staged": staged,
            "modified": modified,
            "untracked": untracked
        }
        
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Git error: {e}")
        return {"staged": [], "modified": [], "untracked": []}


 