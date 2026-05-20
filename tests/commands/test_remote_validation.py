"""Tests for remote validation configuration."""

import json
import yaml
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.config import config
import requests


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
    
    # Create datasets directory
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir()
    
    return tmp_path


@pytest.fixture
def sample_remote_config():
    """Sample remote validation configuration."""
    return {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name",
                "description",
                "creator",
                "dateCreated",
                "distribution",
                "license"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1},
                "license": {"type": "string", "min_length": 5}
            }
        }
    }


@mock.patch("biotope.commands.config._find_biotope_root")
def test_set_remote_validation(mock_find_root, runner, biotope_project):
    """Test setting remote validation configuration."""
    mock_find_root.return_value = biotope_project
    
    # Create initial config
    config_file = biotope_project / ".biotope" / "config.yaml"
    initial_config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": ["name", "description"]
        }
    }
    with open(config_file, "w") as f:
        yaml.dump(initial_config, f)
    
    # Mock the remote configuration test
    with mock.patch("biotope.validation._load_remote_validation_config") as mock_load_remote:
        mock_load_remote.return_value = {
            "minimum_required_fields": ["name", "description", "creator"],
            "field_validation": {
                "creator": {"type": "object", "required_keys": ["name"]}
            }
        }
        
        # Run the command
        result = runner.invoke(config, [
            "set-remote-validation",
            "--url", "https://cluster.example.com/validation.yaml",
            "--cache-duration", "7200",
            "--fallback-to-local"
        ])
        
        assert result.exit_code == 0
        assert "Set remote validation URL" in result.output
        assert "https://cluster.example.com/validation.yaml" in result.output
        assert "Cache duration: 7200 seconds" in result.output
        
        # Check that config was updated
        with open(config_file) as f:
            updated_config = yaml.safe_load(f)
        
        remote_config = updated_config["annotation_validation"]["remote_config"]
        assert remote_config["url"] == "https://cluster.example.com/validation.yaml"
        assert remote_config["cache_duration"] == 7200
        assert remote_config["fallback_to_local"] is True


@mock.patch("biotope.commands.config._find_biotope_root")
def test_remove_remote_validation(mock_find_root, runner, biotope_project):
    """Test removing remote validation configuration."""
    mock_find_root.return_value = biotope_project
    
    # Create config with remote validation
    config_file = biotope_project / ".biotope" / "config.yaml"
    initial_config = {
        "annotation_validation": {
            "enabled": True,
            "remote_config": {
                "url": "https://cluster.example.com/validation.yaml",
                "cache_duration": 3600,
                "fallback_to_local": True
            }
        }
    }
    with open(config_file, "w") as f:
        yaml.dump(initial_config, f)
    
    # Run the command
    result = runner.invoke(config, ["remove-remote-validation"])
    
    assert result.exit_code == 0
    assert "Removed remote validation configuration" in result.output
    
    # Check that config was updated
    with open(config_file) as f:
        updated_config = yaml.safe_load(f)
    
    assert "remote_config" not in updated_config["annotation_validation"]


@mock.patch("biotope.commands.config._find_biotope_root")
def test_clear_validation_cache(mock_find_root, runner, biotope_project):
    """Test clearing validation cache."""
    mock_find_root.return_value = biotope_project
    
    # Create cache directory and file
    cache_dir = biotope_project / ".biotope" / "cache" / "validation"
    cache_dir.mkdir(parents=True)
    cache_file = cache_dir / "test_cache.yaml"
    cache_file.write_text("test content")
    
    # Run the command
    result = runner.invoke(config, ["clear-validation-cache"])
    
    assert result.exit_code == 0
    assert "Cleared validation cache" in result.output
    
    # Check that cache was removed
    assert not cache_dir.exists()


@mock.patch("biotope.commands.config._find_biotope_root")
def test_show_remote_validation(mock_find_root, runner, biotope_project):
    """Test showing remote validation configuration."""
    mock_find_root.return_value = biotope_project
    
    # Create config with remote validation
    config_file = biotope_project / ".biotope" / "config.yaml"
    initial_config = {
        "annotation_validation": {
            "enabled": True,
            "remote_config": {
                "url": "https://cluster.example.com/validation.yaml",
                "cache_duration": 3600,
                "fallback_to_local": True
            },
            "minimum_required_fields": ["name", "description", "creator"]
        }
    }
    with open(config_file, "w") as f:
        yaml.dump(initial_config, f)
    
    # Mock the cache file check
    with mock.patch("biotope.validation._get_cache_file_path") as mock_cache_path:
        mock_cache_file = biotope_project / ".biotope" / "cache" / "validation" / "test.yaml"
        mock_cache_path.return_value = mock_cache_file
        
        # Mock the cache file stats
        with mock.patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with mock.patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value = mock.Mock(st_mtime=1234567890)
                
                # Run the command
                result = runner.invoke(config, ["show-remote-validation"])
                
                assert result.exit_code == 0
                assert "Remote Validation Configuration" in result.output
                assert "https://cluster.example.com/validation.yaml" in result.output
                assert "Cache Duration: 3600 seconds" in result.output
                assert "Fallback to Local: True" in result.output


@mock.patch("biotope.commands.config._find_biotope_root")
def test_show_remote_validation_no_config(mock_find_root, runner, biotope_project):
    """Test showing remote validation when no config exists."""
    mock_find_root.return_value = biotope_project
    
    # Create empty config
    config_file = biotope_project / ".biotope" / "config.yaml"
    initial_config = {"annotation_validation": {"enabled": True}}
    with open(config_file, "w") as f:
        yaml.dump(initial_config, f)
    
    # Run the command
    result = runner.invoke(config, ["show-remote-validation"])
    
    assert result.exit_code == 0
    assert "No remote validation configuration" in result.output
    assert "set-remote-validation" in result.output


def test_merge_validation_configs():
    """Test merging remote and local validation configurations."""
    from biotope.validation import _merge_validation_configs
    
    remote_config = {
        "minimum_required_fields": ["name", "description", "creator"],
        "field_validation": {
            "name": {"type": "string", "min_length": 1},
            "creator": {"type": "object", "required_keys": ["name"]}
        }
    }
    
    local_config = {
        "minimum_required_fields": ["license"],
        "field_validation": {
            "license": {"type": "string", "min_length": 5}
        },
        "enabled": True
    }
    
    merged = _merge_validation_configs(remote_config, local_config)
    
    # Check that fields are merged (union)
    expected_fields = ["name", "description", "creator", "license"]
    assert set(merged["minimum_required_fields"]) == set(expected_fields)
    
    # Check that field validation is merged (local overrides remote)
    expected_validation = {
        "name": {"type": "string", "min_length": 1},
        "creator": {"type": "object", "required_keys": ["name"]},
        "license": {"type": "string", "min_length": 5}
    }
    assert merged["field_validation"] == expected_validation
    
    # Check that other local settings are preserved
    assert merged["enabled"] is True


@mock.patch("requests.get")
def test_load_remote_validation_config(mock_get, biotope_project, sample_remote_config):
    """Test loading remote validation configuration."""
    from biotope.validation import _load_remote_validation_config
    
    # Mock successful response
    mock_response = mock.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.text = yaml.dump(sample_remote_config)
    mock_get.return_value = mock_response
    
    remote_config = {
        "url": "https://cluster.example.com/validation.yaml",
        "cache_duration": 3600,
        "fallback_to_local": True
    }
    
    result = _load_remote_validation_config(remote_config, biotope_project)
    
    assert result is not None
    assert result["annotation_validation"]["minimum_required_fields"] == [
        "name", "description", "creator", "dateCreated", "distribution", "license"
    ]
    
    # Check that cache file was created
    cache_file = biotope_project / ".biotope" / "cache" / "validation" / "cluster_example_com_validation.yaml"
    
    # Debug: Check if cache directory exists
    cache_dir = cache_file.parent
    print(f"Cache directory exists: {cache_dir.exists()}")
    print(f"Cache directory path: {cache_dir}")
    
    # Debug: Check if cache file exists
    print(f"Cache file exists: {cache_file.exists()}")
    print(f"Cache file path: {cache_file}")
    
    # Debug: List contents of cache directory if it exists
    if cache_dir.exists():
        print(f"Cache directory contents: {list(cache_dir.iterdir())}")
    
    assert cache_file.exists()
    
    # Verify the cache file contains the expected data
    with open(cache_file) as f:
        cached_data = yaml.safe_load(f)
    assert cached_data == sample_remote_config


@mock.patch("requests.get")
def test_load_remote_validation_config_fallback(mock_get, biotope_project):
    """Test fallback behavior when remote config fails."""
    from biotope.validation import _load_remote_validation_config
    
    # Mock failed response
    mock_get.side_effect = requests.RequestException("Network error")
    
    remote_config = {
        "url": "https://cluster.example.com/validation.yaml",
        "cache_duration": 3600,
        "fallback_to_local": True
    }
    
    result = _load_remote_validation_config(remote_config, biotope_project)
    
    # Should return None when fallback is enabled
    assert result is None


@mock.patch("requests.get")
def test_load_remote_validation_config_no_fallback(mock_get, biotope_project):
    """Test error when remote config fails and fallback is disabled."""
    from biotope.validation import _load_remote_validation_config

    # Mock failed response
    mock_get.side_effect = requests.RequestException("Network error")

    remote_config = {
        "url": "https://cluster.example.com/validation.yaml",
        "cache_duration": 3600,
        "fallback_to_local": False
    }

    with pytest.raises(ValueError, match="Failed to load remote validation config"):
        _load_remote_validation_config(remote_config, biotope_project) 