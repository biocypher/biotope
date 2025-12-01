"""Unit tests for biotope utilities."""

import yaml
from unittest.mock import patch

from biotope.utils import find_biotope_root, is_git_repo, load_project_metadata


def test_find_biotope_root(tmp_path):
    """Test finding biotope root directory."""
    # Create a nested directory structure
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    
    biotope_dir = project_dir / ".biotope"
    biotope_dir.mkdir()
    git_dir = project_dir / ".git"
    git_dir.mkdir()
    
    # Test from project root
    with patch("biotope.utils.Path.cwd", return_value=project_dir):
        result = find_biotope_root()
        assert result == project_dir
    
    # Test from subdirectory
    subdir = project_dir / "subdir"
    subdir.mkdir()
    
    with patch("biotope.utils.Path.cwd", return_value=subdir):
        result = find_biotope_root()
        assert result == project_dir
    
    # Test from outside project
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    
    with patch("biotope.utils.Path.cwd", return_value=outside_dir):
        result = find_biotope_root()
        assert result is None
    
    # Test .biotope without .git (should fail)
    invalid_project_dir = tmp_path / "invalid_project"
    invalid_project_dir.mkdir()
    invalid_biotope_dir = invalid_project_dir / ".biotope"
    invalid_biotope_dir.mkdir()
    
    with patch("biotope.utils.Path.cwd", return_value=invalid_project_dir):
        result = find_biotope_root()
        assert result is None


def test_is_git_repo(tmp_path):
    """Test checking if directory is a git repository."""
    # Test non-git directory
    assert not is_git_repo(tmp_path)
    
    # Test git directory
    git_dir = tmp_path / "git_project"
    git_dir.mkdir()
    
    # Initialize a proper git repository
    import subprocess
    subprocess.run(["git", "init"], cwd=git_dir, check=True)
    
    assert is_git_repo(git_dir)


def test_load_project_metadata(tmp_path):
    """Test loading project metadata from configuration."""
    # Create a mock biotope project structure
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    biotope_dir = project_dir / ".biotope"
    biotope_dir.mkdir()
    
    config_dir = biotope_dir / "config"
    config_dir.mkdir()
    
    # Create config with project metadata
    config_data = {
        "version": "1.0",
        "project_metadata": {
            "description": "Test project description",
            "url": "https://example.com",
            "creator": "test@example.com",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "citation": "Please cite this dataset as: {name} ({year})",
            "project_name": "test_project",
            "access_restrictions": "Public",
            "legal_obligations": "None",
            "collaboration_partner": "Test Institute"
        }
    }
    
    config_file = config_dir / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    # Test loading project metadata
    result = load_project_metadata(project_dir)
    
    assert result["description"] == "Test project description"
    assert result["url"] == "https://example.com"
    assert result["creator"]["name"] == "test@example.com"
    assert result["creator"]["@type"] == "Person"
    assert result["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert result["citation"] == "Please cite this dataset as: {name} ({year})"
    assert result["cr:projectName"] == "test_project"
    assert result["cr:accessRestrictions"] == "Public"
    assert result["cr:legalObligations"] == "None"
    assert result["cr:collaborationPartner"] == "Test Institute"


def test_load_project_metadata_no_config(tmp_path):
    """Test loading project metadata when no config exists."""
    # Create a directory without config
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    result = load_project_metadata(project_dir)
    assert result == {}


def test_load_project_metadata_no_project_metadata(tmp_path):
    """Test loading project metadata when config exists but no project_metadata section."""
    # Create a mock biotope project structure
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    biotope_dir = project_dir / ".biotope"
    biotope_dir.mkdir()
    
    config_dir = biotope_dir / "config"
    config_dir.mkdir()
    
    # Create config without project metadata
    config_data = {
        "version": "1.0",
        "annotation_validation": {
            "enabled": True
        }
    }
    
    config_file = config_dir / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    # Test loading project metadata
    result = load_project_metadata(project_dir)
    assert result == {}


def test_load_project_metadata_partial_data(tmp_path):
    """Test loading project metadata with only some fields present."""
    # Create a mock biotope project structure
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    biotope_dir = project_dir / ".biotope"
    biotope_dir.mkdir()
    
    config_dir = biotope_dir / "config"
    config_dir.mkdir()
    
    # Create config with partial project metadata
    config_data = {
        "version": "1.0",
        "project_metadata": {
            "description": "Test project description",
            "creator": "test@example.com"
        }
    }
    
    config_file = config_dir / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    # Test loading project metadata
    result = load_project_metadata(project_dir)
    
    assert result["description"] == "Test project description"
    assert result["creator"]["name"] == "test@example.com"
    assert result["creator"]["@type"] == "Person"
    
    # Check that missing fields are not present
    assert "url" not in result
    assert "license" not in result
    assert "citation" not in result 