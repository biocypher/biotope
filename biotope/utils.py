"""Shared utility functions for biotope commands."""

import subprocess
from pathlib import Path
from typing import Optional


def find_biotope_root() -> Optional[Path]:
    """
    Find the biotope project root directory.
    
    Searches upward from the current working directory to find a directory
    containing a .biotope/ subdirectory.
    
    Returns:
        Path to the biotope project root, or None if not found
    """
    current = Path.cwd()
    while current != current.parent:
        if (current / ".biotope").exists():
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
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False 


def load_project_metadata(biotope_root: Path) -> dict:
    """Load project-level metadata from biotope configuration for pre-filling annotations."""
    config_path = biotope_root / ".biotope" / "config" / "biotope.yaml"
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
            "name": project_metadata["creator"]
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