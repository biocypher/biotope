"""Shared utility functions for biotope commands."""

import hashlib
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Optional

import click


def find_biotope_root(start: Path | None = None) -> Optional[Path]:
    """
    Find the biotope project root directory.

    Searches upward from ``start`` (default: current working directory) to find
    a directory containing a .biotope/ subdirectory. Git is optional.

    Args:
        start: Directory to begin the upward search from. Defaults to ``Path.cwd()``.

    Returns:
        Path to the biotope project root, or None if not found
    """
    current = (start if start is not None else Path.cwd()).resolve()
    while current != current.parent:
        if (current / ".biotope").is_dir():
            return current
        current = current.parent
    return None


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
        croissant_metadata["cr:accessRestrictions"] = project_metadata["access_restrictions"]

    if project_metadata.get("legal_obligations"):
        croissant_metadata["cr:legalObligations"] = project_metadata["legal_obligations"]

    if project_metadata.get("collaboration_partner"):
        croissant_metadata["cr:collaborationPartner"] = project_metadata["collaboration_partner"]

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


def ignored_by_git(root: Path, paths: Iterable[Path]) -> list[str]:
    base = root.resolve()
    resolved = [(root / path).resolve() for path in paths]
    relative = sorted({path.relative_to(base).as_posix() for path in resolved if path.is_relative_to(base)})
    if not relative or shutil.which("git") is None:
        return []
    checked = subprocess.run(
        ["git", "check-ignore", "--stdin", "-z"], cwd=root, input="\0".join(relative), capture_output=True, text=True
    )
    return sorted(path for path in checked.stdout.split("\0") if path) if checked.returncode == 0 else []


def unreported(root: Path, ignored: Iterable[str]) -> list[str]:
    context = click.get_current_context(silent=True)
    reported: set[Path] = set() if context is None else context.meta.setdefault("biotope.reported_ignored", set())
    fresh = [path for path in ignored if root.resolve() / path not in reported]
    reported.update(root.resolve() / path for path in fresh)
    return fresh


def warn_ignored(root: Path, paths: Iterable[Path]) -> None:
    for path in unreported(root, ignored_by_git(root, paths)):
        click.echo(
            f"Warning: git ignores {path}. Commit it with the project: add an exception to .gitignore.", err=True
        )
