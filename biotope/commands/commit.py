"""Commit command implementation using Git under the hood."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import click
import yaml

from biotope.utils import find_biotope_root, is_git_repo


@click.command()
@click.option(
    "--message",
    "-m",
    required=True,
    help="Commit message describing the changes",
)
@click.option(
    "--author",
    "-a",
    help="Author of the commit (defaults to current user)",
)
@click.option(
    "--no-verify",
    is_flag=True,
    help="Skip validation of metadata files",
)
@click.option(
    "--amend",
    is_flag=True,
    help="Amend the previous commit",
)
def commit(message: str, author: Optional[str], no_verify: bool, amend: bool) -> None:
    """
    Commit staged files and metadata changes using Git.
    
    Creates a Git commit for the .biotope/ directory changes.
    Similar to git commit but focused on metadata.
    
    Args:
        message: Commit message describing the changes
        author: Author of the commit
        no_verify: Skip validation of metadata files
        amend: Amend the previous commit
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

    # Validate metadata if requested
    if not no_verify:
        if not _validate_metadata_files(biotope_root):
            click.echo("❌ Metadata validation failed. Use --no-verify to skip.")
            raise click.Abort

    # Stage .biotope/ directory changes
    if not _stage_biotope_changes(biotope_root):
        click.echo("❌ No changes to commit in .biotope/ directory.")
        raise click.Abort

    # Create Git commit
    commit_hash = _create_git_commit(biotope_root, message, author, amend)
    
    if commit_hash:
        click.echo(f"✅ Commit {commit_hash[:8]} created successfully!")
        click.echo(f"  Message: {message}")
        click.echo(f"  Files: .biotope/")
    else:
        click.echo("❌ Failed to create commit.")





def _validate_metadata_files(biotope_root: Path) -> bool:
    """Validate all Croissant ML files in .biotope/datasets/."""
    datasets_dir = biotope_root / ".biotope" / "datasets"
    
    if not datasets_dir.exists():
        return True  # No datasets to validate
    
    for dataset_file in datasets_dir.rglob("*.jsonld"):
        try:
            with open(dataset_file) as f:
                metadata = json.load(f)
            
            # Basic validation - check required fields
            if not metadata.get("@type") == "Dataset":
                click.echo(f"⚠️  Warning: {dataset_file.name} missing @type: Dataset")
            
            if not metadata.get("name"):
                click.echo(f"⚠️  Warning: {dataset_file.name} missing name field")
                
        except json.JSONDecodeError as e:
            click.echo(f"❌ Invalid JSON in {dataset_file.name}: {e}")
            return False
        except Exception as e:
            click.echo(f"❌ Error validating {dataset_file.name}: {e}")
            return False
    
    return True


def _stage_biotope_changes(biotope_root: Path) -> bool:
    """Stage changes in .biotope/ directory."""
    try:
        # Check if there are changes to stage
        result = subprocess.run(
            ["git", "status", "--porcelain", ".biotope/"],
            cwd=biotope_root,
            capture_output=True,
            text=True,
            check=True
        )
        
        if not result.stdout.strip():
            return False
        
        # Stage all changes in .biotope/
        subprocess.run(
            ["git", "add", ".biotope/"],
            cwd=biotope_root,
            check=True
        )
        
        return True
        
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Git error: {e}")
        return False


def _create_git_commit(
    biotope_root: Path, 
    message: str, 
    author: Optional[str], 
    amend: bool
) -> Optional[str]:
    """Create a Git commit for .biotope/ changes."""
    try:
        # Build commit command
        cmd = ["git", "commit"]
        
        if amend:
            cmd.append("--amend")
        
        if author:
            cmd.extend(["--author", author])
        
        cmd.extend(["-m", message])
        
        # Execute commit
        result = subprocess.run(
            cmd,
            cwd=biotope_root,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Extract commit hash from output
        for line in result.stdout.splitlines():
            if line.startswith("[") and "]" in line:
                # Extract hash from output like "[main abc1234] message"
                parts = line.split("]")[0].split()
                if len(parts) >= 2:
                    return parts[1]
        
        # Fallback: get latest commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=biotope_root,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
        
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Git commit failed: {e}")
        if e.stderr:
            click.echo(f"Error details: {e.stderr}")
        return None


 