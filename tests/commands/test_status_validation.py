"""Tests for status command annotation validation display."""

import json
from unittest import mock
import yaml

import pytest
from click.testing import CliRunner
import os

from biotope.commands.status import status


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def biotope_project(tmp_path):
    """Create a mock biotope project structure."""
    # Create .biotope directory
    biotope_dir = tmp_path / ".biotope"
    biotope_dir.mkdir()
    
    # Create config directory
    config_dir = biotope_dir / "config"
    config_dir.mkdir()
    
    # Create datasets directory
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir()
    
    return tmp_path


@pytest.fixture
def git_repo(biotope_project):
    """Create a mock Git repository."""
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        yield biotope_project


def test_status_shows_annotation_status_for_add_metadata(runner, git_repo):
    """Test that status shows incomplete annotation for biotope add metadata."""
    
    # Create biotope config with default validation
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description", 
                "creator",
                "dateCreated",
                "distribution"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1}
            }
        }
    }
    
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    # Create metadata file like biotope add would (incomplete)
    incomplete_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "experiment3",
        "description": "Dataset for experiment3.csv",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_e3b0c442",
                "name": "experiment3.csv",
                "contentUrl": "data/raw/experiment3.csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "contentSize": 0,
                "dateCreated": "2025-07-15T14:57:55.699579+00:00"
            }
        ]
    }
    
    metadata_file = git_repo / ".biotope" / "datasets" / "experiment3.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(incomplete_metadata, f)
    
    # Mock Git status to show this file as tracked
    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={
             "staged": [],
             "modified": [],
             "untracked": []
         }):
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            # Run status command in the correct working directory
            result = runner.invoke(status)
            # Should show the file as unannotated (⚠️)
            assert result.exit_code == 0
            assert "experiment3" in result.output
            assert "⚠️" in result.output or "Incomplete" in result.output


def test_status_shows_annotation_status_for_complete_metadata(runner, git_repo):
    """Test that status shows complete annotation for properly annotated metadata."""
    
    # Create biotope config with default validation
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description", 
                "creator",
                "dateCreated",
                "distribution"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1}
            }
        }
    }
    
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    # Create complete metadata file
    complete_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "experiment3",
        "description": "Dataset for experiment3.csv with complete annotation",
        "creator": {
            "name": "John Doe",
            "email": "john@example.com"
        },
        "dateCreated": "2025-07-15T14:57:55.699579+00:00",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_e3b0c442",
                "name": "experiment3.csv",
                "contentUrl": "data/raw/experiment3.csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "contentSize": 0,
                "dateCreated": "2025-07-15T14:57:55.699579+00:00"
            }
        ]
    }
    
    metadata_file = git_repo / ".biotope" / "datasets" / "experiment3.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(complete_metadata, f)
    
    # Mock Git status to show this file as tracked
    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={
             "staged": [],
             "modified": [],
             "untracked": []
         }):
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            # Run status command in the correct working directory
            result = runner.invoke(status)
            # Should show the file as annotated (✅)
            assert result.exit_code == 0
            assert "experiment3" in result.output
            assert "✅" in result.output or "Complete" in result.output 


def test_status_suggests_annotate_for_incomplete_staged_metadata(runner, git_repo):
    """Test that status suggests annotate command for staged metadata with incomplete annotations."""
    
    # Create biotope config with default validation
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description", 
                "creator",
                "dateCreated",
                "distribution"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1}
            }
        }
    }
    
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    # Create incomplete metadata file
    incomplete_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "experiment3",
        "description": "Dataset for experiment3.csv",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_e3b0c442",
                "name": "experiment3.csv",
                "contentUrl": "data/raw/experiment3.csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "contentSize": 0,
                "dateCreated": "2025-07-15T14:57:55.699579+00:00"
            }
        ]
    }
    
    metadata_file = git_repo / ".biotope" / "datasets" / "experiment3.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(incomplete_metadata, f)
    
    # Mock Git status to show this file as staged
    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={
             "staged": [("A", ".biotope/datasets/experiment3.jsonld")],
             "modified": [],
             "untracked": []
         }), \
         mock.patch("subprocess.run") as mock_subprocess:
        # Mock the git diff --cached --name-only call in get_staged_metadata_files
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ".biotope/datasets/experiment3.jsonld\n"
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            # Run status command in the correct working directory
            result = runner.invoke(status)
            # Should suggest annotate command for incomplete staged metadata
            assert result.exit_code == 0
            assert "biotope annotate interactive --staged" in result.output
            assert "staged file" in result.output or "staged files" in result.output


def test_status_does_not_suggest_annotate_for_complete_staged_metadata(runner, git_repo):
    """Test that status does not suggest annotate command for staged metadata with complete annotations."""
    
    # Create biotope config with default validation
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description", 
                "creator",
                "dateCreated",
                "distribution"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1}
            }
        }
    }
    
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    # Create complete metadata file
    complete_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "experiment3",
        "description": "Dataset for experiment3.csv with complete annotation",
        "creator": {
            "name": "John Doe",
            "email": "john@example.com"
        },
        "dateCreated": "2025-07-15T14:57:55.699579+00:00",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_e3b0c442",
                "name": "experiment3.csv",
                "contentUrl": "data/raw/experiment3.csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "contentSize": 0,
                "dateCreated": "2025-07-15T14:57:55.699579+00:00"
            }
        ]
    }
    
    metadata_file = git_repo / ".biotope" / "datasets" / "experiment3.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(complete_metadata, f)
    
    # Mock Git status to show this file as staged
    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={
             "staged": [("A", ".biotope/datasets/experiment3.jsonld")],
             "modified": [],
             "untracked": []
         }), \
         mock.patch("subprocess.run") as mock_subprocess:
        # Mock the git diff --cached --name-only call in get_staged_metadata_files
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ".biotope/datasets/experiment3.jsonld\n"
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            # Run status command in the correct working directory
            result = runner.invoke(status)
            # Should NOT suggest annotate command for complete staged metadata
            assert result.exit_code == 0
            assert "biotope annotate interactive --staged" not in result.output
            assert "staged file" not in result.output and "staged files" not in result.output
            # Should still suggest commit
            assert "biotope commit" in result.output


def test_status_suggests_annotate_for_incomplete_tracked_metadata(runner, git_repo):
    """Test that status suggests annotate --incomplete command for tracked metadata with incomplete annotations."""
    
    # Create biotope config with default validation
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description", 
                "creator",
                "dateCreated",
                "distribution"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1}
            }
        }
    }
    
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    # Create incomplete metadata file
    incomplete_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "experiment3",
        "description": "Dataset for experiment3.csv",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_e3b0c442",
                "name": "experiment3.csv",
                "contentUrl": "data/raw/experiment3.csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "contentSize": 0,
                "dateCreated": "2025-07-15T14:57:55.699579+00:00"
            }
        ]
    }
    
    metadata_file = git_repo / ".biotope" / "datasets" / "experiment3.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(incomplete_metadata, f)
    
    # Mock Git status to show no staged/modified/untracked files
    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={
             "staged": [],
             "modified": [],
             "untracked": []
         }), \
         mock.patch("subprocess.run") as mock_subprocess:
        # Mock the git diff --cached --name-only call in get_staged_metadata_files
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            # Run status command in the correct working directory
            result = runner.invoke(status)
            # Should suggest annotate --incomplete command for incomplete tracked metadata
            assert result.exit_code == 0
            assert "biotope annotate interactive --incomplete" in result.output
            assert "tracked file" in result.output or "tracked files" in result.output


def test_status_does_not_suggest_annotate_for_complete_tracked_metadata(runner, git_repo):
    """Test that status does not suggest annotate --incomplete command for tracked metadata with complete annotations."""
    
    # Create biotope config with default validation
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description", 
                "creator",
                "dateCreated",
                "distribution"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1}
            }
        }
    }
    
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    # Create complete metadata file
    complete_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "experiment3",
        "description": "Dataset for experiment3.csv with complete annotation",
        "creator": {
            "name": "John Doe",
            "email": "john@example.com"
        },
        "dateCreated": "2025-07-15T14:57:55.699579+00:00",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_e3b0c442",
                "name": "experiment3.csv",
                "contentUrl": "data/raw/experiment3.csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "contentSize": 0,
                "dateCreated": "2025-07-15T14:57:55.699579+00:00"
            }
        ]
    }
    
    metadata_file = git_repo / ".biotope" / "datasets" / "experiment3.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(complete_metadata, f)
    
    # Mock Git status to show no staged/modified/untracked files
    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={
             "staged": [],
             "modified": [],
             "untracked": []
         }), \
         mock.patch("subprocess.run") as mock_subprocess:
        # Mock the git diff --cached --name-only call in get_staged_metadata_files
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            # Run status command in the correct working directory
            result = runner.invoke(status)
            # Should NOT suggest annotate --incomplete command for complete tracked metadata
            assert result.exit_code == 0
            assert "biotope annotate interactive --incomplete" not in result.output
            assert "tracked file" not in result.output and "tracked files" not in result.output


def test_status_shows_suggestions_for_both_staged_and_tracked_incomplete(runner, git_repo):
    """Test that status suggests annotation for both staged and tracked incomplete files if both exist."""
    
    # Create biotope config with default validation
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description", 
                "creator",
                "dateCreated",
                "distribution"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1}
            }
        }
    }
    
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    # Create incomplete tracked metadata file
    incomplete_tracked_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "tracked_incomplete",
        "description": "Dataset for tracked_incomplete.csv",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_tracked",
                "name": "tracked_incomplete.csv",
                "contentUrl": "data/raw/tracked_incomplete.csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "contentSize": 0,
                "dateCreated": "2025-07-15T14:57:55.699579+00:00"
            }
        ]
    }
    
    tracked_metadata_file = git_repo / ".biotope" / "datasets" / "tracked_incomplete.jsonld"
    with open(tracked_metadata_file, "w") as f:
        json.dump(incomplete_tracked_metadata, f)
    
    # Create incomplete staged metadata file
    incomplete_staged_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "staged_incomplete",
        "description": "Dataset for staged_incomplete.csv",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_staged",
                "name": "staged_incomplete.csv",
                "contentUrl": "data/raw/staged_incomplete.csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "contentSize": 0,
                "dateCreated": "2025-07-15T14:57:55.699579+00:00"
            }
        ]
    }
    
    staged_metadata_file = git_repo / ".biotope" / "datasets" / "staged_incomplete.jsonld"
    with open(staged_metadata_file, "w") as f:
        json.dump(incomplete_staged_metadata, f)
    
    # Mock Git status to show staged file
    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={
             "staged": [("A", ".biotope/datasets/staged_incomplete.jsonld")],
             "modified": [],
             "untracked": []
         }), \
         mock.patch("subprocess.run") as mock_subprocess:
        # Mock the git diff --cached --name-only call in get_staged_metadata_files
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ".biotope/datasets/staged_incomplete.jsonld\n"
        
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            # Run status command in the correct working directory
            result = runner.invoke(status)
            # Should suggest --staged when there are incomplete staged files
            assert result.exit_code == 0
            assert "biotope annotate interactive --staged" in result.output
            assert "staged file" in result.output or "staged files" in result.output
            # Should also suggest --incomplete if both exist
            assert "biotope annotate interactive --incomplete" in result.output
            assert "tracked file" in result.output or "tracked files" in result.output 

def test_status_detailed_shows_errors_for_incomplete_metadata(runner, git_repo):
    """Test that status --detailed shows validation errors for incomplete metadata."""
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": ["name", "description", "creator"],
        }
    }
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)

    incomplete_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "experiment",
    }
    metadata_file = git_repo / ".biotope" / "datasets" / "experiment.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(incomplete_metadata, f)

    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={"staged": [], "modified": [], "untracked": []}):
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            result = runner.invoke(status, ["--detailed"])
            assert result.exit_code == 0
            assert "Validation Issues" in result.output
            assert "description" in result.output
            assert "creator" in result.output

def test_status_detailed_shows_no_errors_when_validation_disabled(runner, git_repo):
    """Test that status --detailed shows no validation errors when validation is disabled."""
    config = {
        "annotation_validation": {
            "enabled": False,  # Validation is disabled
            "minimum_required_fields": ["name", "description", "creator"],
        }
    }
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)

    # This metadata is incomplete based on the rules, but validation is off
    incomplete_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "experiment",
    }
    metadata_file = git_repo / ".biotope" / "datasets" / "experiment.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(incomplete_metadata, f)

    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={"staged": [], "modified": [], "untracked": []}):
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            result = runner.invoke(status, ["--detailed"])
            assert result.exit_code == 0
            assert "Validation Issues" not in result.output
            assert "Complete" in result.output
            assert "Incomplete" not in result.output

def test_status_no_detailed_suggests_detailed_for_incomplete_metadata(runner, git_repo):
    """Test that status without --detailed suggests running with --detailed for incomplete metadata."""
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": ["name", "description", "creator"],
        }
    }
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)

    incomplete_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "experiment",
    }
    metadata_file = git_repo / ".biotope" / "datasets" / "experiment.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(incomplete_metadata, f)

    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={"staged": [], "modified": [], "untracked": []}):
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            result = runner.invoke(status)
            assert result.exit_code == 0
            assert "Validation Issues" not in result.output
            assert "biotope status --detailed" in result.output

def test_status_detailed_shows_no_errors_for_complete_metadata(runner, git_repo):
    """Test that status --detailed shows no validation errors for complete metadata."""
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": ["name", "description", "creator"],
        }
    }
    config_file = git_repo / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)

    complete_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "experiment",
        "description": "A complete description.",
        "creator": {"name": "Test User"},
    }
    metadata_file = git_repo / ".biotope" / "datasets" / "experiment.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(complete_metadata, f)

    with mock.patch("biotope.utils.find_biotope_root", return_value=git_repo), \
         mock.patch("biotope.commands.status._get_git_status", return_value={"staged": [], "modified": [], "untracked": []}):
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            result = runner.invoke(status, ["--detailed"])
            assert result.exit_code == 0
            assert "Validation Issues" not in result.output
