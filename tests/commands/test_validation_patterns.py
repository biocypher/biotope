"""Tests for validation pattern functionality."""

from unittest import mock

import pytest
import yaml
from click.testing import CliRunner

from biotope.commands.config import config
from biotope.validation import get_validation_info, get_validation_pattern


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

    # Create initial config
    initial_config = {
        "version": "1.0",
        "annotation_validation": {
            "enabled": True,
            "validation_pattern": "default",
            "minimum_required_fields": ["name", "description", "creator"],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "creator": {"type": "object", "required_keys": ["name"]},
            },
        },
    }

    config_file = biotope_dir / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(initial_config, f)

    return tmp_path


@mock.patch("biotope.commands.config._find_biotope_root")
def test_set_validation_pattern(mock_find_root, runner, biotope_project):
    """Test setting validation pattern."""
    mock_find_root.return_value = biotope_project

    # Set validation pattern
    result = runner.invoke(config, ["set-validation-pattern", "--pattern", "cluster-strict"])

    assert result.exit_code == 0
    assert "Set validation pattern to: cluster-strict" in result.output

    # Check that config was updated
    config_file = biotope_project / ".biotope" / "config.yaml"
    with open(config_file) as f:
        updated_config = yaml.safe_load(f)

    assert updated_config["annotation_validation"]["validation_pattern"] == "cluster-strict"


@mock.patch("biotope.commands.config._find_biotope_root")
def test_show_validation_pattern(mock_find_root, runner, biotope_project):
    """Test showing validation pattern information."""
    mock_find_root.return_value = biotope_project

    # Show validation pattern
    result = runner.invoke(config, ["show-validation-pattern"])

    assert result.exit_code == 0
    assert "Validation Pattern Information" in result.output
    assert "Pattern: default" in result.output
    assert "Remote Validation: ❌ Not configured" in result.output


@mock.patch("biotope.commands.config._find_biotope_root")
def test_show_validation_pattern_with_remote(mock_find_root, runner, biotope_project):
    """Test showing validation pattern with remote validation configured."""
    mock_find_root.return_value = biotope_project

    # Update config to include remote validation
    config_file = biotope_project / ".biotope" / "config.yaml"
    with open(config_file) as f:
        config_data = yaml.safe_load(f)

    config_data["annotation_validation"]["remote_config"] = {
        "url": "https://cluster.example.com/validation/cluster-strict",
        "cache_duration": 3600,
        "fallback_to_local": True,
    }

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Show validation pattern
    result = runner.invoke(config, ["show-validation-pattern"])

    assert result.exit_code == 0
    assert "Validation Pattern Information" in result.output
    assert "Pattern: cluster-default" in result.output  # Should be auto-detected
    assert "Remote Validation: ✅ Configured" in result.output
    assert "https://cluster.example.com/validation/cluster-strict" in result.output


def test_get_validation_pattern_default(biotope_project):
    """Test getting validation pattern with default configuration."""
    pattern = get_validation_pattern(biotope_project)
    assert pattern == "default"


def test_get_validation_pattern_explicit(biotope_project):
    """Test getting validation pattern with explicit configuration."""
    # Update config
    config_file = biotope_project / ".biotope" / "config.yaml"
    with open(config_file) as f:
        config_data = yaml.safe_load(f)

    config_data["annotation_validation"]["validation_pattern"] = "storage-management"

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    pattern = get_validation_pattern(biotope_project)
    assert pattern == "storage-management"


def test_get_validation_pattern_with_remote_cluster(biotope_project):
    """Test getting validation pattern with cluster remote validation."""
    # Update config with cluster remote validation
    config_file = biotope_project / ".biotope" / "config.yaml"
    with open(config_file) as f:
        config_data = yaml.safe_load(f)

    config_data["annotation_validation"]["remote_config"] = {"url": "https://hpc-cluster.example.com/validation/strict"}

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    pattern = get_validation_pattern(biotope_project)
    assert pattern == "cluster-default"  # Should be auto-detected as cluster pattern


def test_get_validation_pattern_with_remote_storage(biotope_project):
    """Test getting validation pattern with storage remote validation."""
    # Update config with storage remote validation
    config_file = biotope_project / ".biotope" / "config.yaml"
    with open(config_file) as f:
        config_data = yaml.safe_load(f)

    config_data["annotation_validation"]["remote_config"] = {
        "url": "https://storage-archive.example.com/validation/archive"
    }

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    pattern = get_validation_pattern(biotope_project)
    assert pattern == "storage-default"  # Should be auto-detected as storage pattern


def test_get_validation_info(biotope_project):
    """Test getting comprehensive validation information."""
    info = get_validation_info(biotope_project)

    assert info["validation_pattern"] == "default"
    assert info["enabled"] is True
    assert info["required_fields"] == ["name", "description", "creator"]
    assert info["remote_configured"] is False
    assert info["remote_url"] is None
    assert "name" in info["field_validation"]


@mock.patch("biotope.validation._load_remote_validation_config")
def test_get_validation_info_with_remote(mock_load_remote, biotope_project):
    """Test getting validation information with remote validation."""
    # Mock the remote validation loading to avoid network requests
    mock_load_remote.return_value = {
        "minimum_required_fields": ["name", "description", "creator", "license"],
        "field_validation": {"license": {"type": "string", "min_length": 5}},
    }

    # Update config with remote validation
    config_file = biotope_project / ".biotope" / "config.yaml"
    with open(config_file) as f:
        config_data = yaml.safe_load(f)

    config_data["annotation_validation"]["remote_config"] = {
        "url": "https://cluster.example.com/validation/strict",
        "cache_duration": 7200,
        "fallback_to_local": False,
    }

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    info = get_validation_info(biotope_project)

    assert info["validation_pattern"] == "cluster-default"
    assert info["remote_configured"] is True
    assert info["remote_url"] == "https://cluster.example.com/validation/strict"
    assert info["cache_duration"] == 7200
    assert info["fallback_to_local"] is False

    # Verify that remote validation was called at least once
    assert mock_load_remote.call_count >= 1


@mock.patch("biotope.commands.config._find_biotope_root")
def test_show_validation_includes_pattern(mock_find_root, runner, biotope_project):
    """Test that show-validation includes validation pattern."""
    mock_find_root.return_value = biotope_project

    # Update config with specific pattern
    config_file = biotope_project / ".biotope" / "config.yaml"
    with open(config_file) as f:
        config_data = yaml.safe_load(f)

    config_data["annotation_validation"]["validation_pattern"] = "cluster-strict"

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Show validation
    result = runner.invoke(config, ["show-validation"])

    assert result.exit_code == 0
    assert "Validation Pattern: cluster-strict" in result.output
    assert "Required Fields:" in result.output
