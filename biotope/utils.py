"""Shared utility functions for biotope commands."""

import hashlib
import subprocess
from pathlib import Path
from typing import Optional

import click


def find_biotope_root() -> Optional[Path]:
    """
    Find the biotope project root directory.

    Searches upward from the current working directory to find a directory
    containing a .biotope/ subdirectory. Enforces that .git and .biotope 
    must be in the same directory.

    Returns:
        Path to the biotope project root, or None if not found
    """
    current = Path.cwd()
    while current != current.parent:
        if (current / ".biotope").exists():
            if not (current / ".git").exists():
                return None
            return current
        current = current.parent
    return None


def is_git_repo(directory: Path) -> bool:
    """
    Check if directory is a Git repository.

    Args:
        directory: Path to the directory to check

    Returns:
        True if the directory is a Git repository, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def load_project_metadata(biotope_root: Path) -> dict:
    """Load project-level metadata from biotope configuration for pre-filling annotations."""
    config_path = biotope_root / ".biotope" / "config.yaml"
    if not config_path.exists():
        return {}

    try:
        import yaml

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except (yaml.YAMLError, IOError):
        return {}

    # Extract project metadata from configuration
    project_metadata = config.get("project_metadata", {})

    # Convert to Croissant format for pre-filling
    croissant_metadata = {}

    if project_metadata.get("description"):
        croissant_metadata["description"] = project_metadata["description"]

    if project_metadata.get("url"):
        croissant_metadata["url"] = project_metadata["url"]

    if project_metadata.get("creator"):
        croissant_metadata["creator"] = {
            "@type": "Person",
            "name": project_metadata["creator"],
        }

    if project_metadata.get("license"):
        croissant_metadata["license"] = project_metadata["license"]

    if project_metadata.get("citation"):
        croissant_metadata["citation"] = project_metadata["citation"]

    if project_metadata.get("project_name"):
        croissant_metadata["cr:projectName"] = project_metadata["project_name"]

    if project_metadata.get("access_restrictions"):
        croissant_metadata["cr:accessRestrictions"] = project_metadata[
            "access_restrictions"
        ]

    if project_metadata.get("legal_obligations"):
        croissant_metadata["cr:legalObligations"] = project_metadata[
            "legal_obligations"
        ]

    if project_metadata.get("collaboration_partner"):
        croissant_metadata["cr:collaborationPartner"] = project_metadata[
            "collaboration_partner"
        ]

    return croissant_metadata


def calculate_file_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def is_file_tracked(file_path: Path, biotope_root: Path) -> bool:
    """Check if a file is tracked in biotope.

    A file counts as tracked if any manifest under ``.biotope/datasets/`` has
    either an explicit ``cr:FileObject`` for it or a ``cr:FileSet`` glob that
    covers it. The latter is the common case after ``biotope add <dir>`` on a
    directory of structured files.
    """
    from biotope.metadata import find_owning_manifest

    if not file_path.is_absolute():
        file_path = file_path.resolve()
    return find_owning_manifest(file_path, biotope_root) is not None


def stage_git_changes(biotope_root: Path) -> None:
    """Stage .biotope/ changes in Git."""
    try:
        subprocess.run(["git", "add", ".biotope/"], cwd=biotope_root, check=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"⚠️  Warning: Could not stage changes in Git: {e}")
