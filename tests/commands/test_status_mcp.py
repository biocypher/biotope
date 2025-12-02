"""Test MCP status functionality in status command."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import yaml

from biotope.commands.status import _get_mcp_status


@pytest.fixture
def biotope_project_with_mcp(tmp_path):
    """Create a biotope project with MCP registry configured."""
    # Create .biotope directory
    biotope_dir = tmp_path / ".biotope"
    biotope_dir.mkdir()
    
    # Create config directory
    config_dir = biotope_dir / "config"
    config_dir.mkdir()
    
    # Create config with MCP registry
    config = {
        "version": "1.0",
        "croissant_schema_version": "1.0",
        "default_metadata_template": "scientific",
        "data_storage": {"type": "local", "path": "data"},
        "checksum_algorithm": "sha256",
        "auto_stage": True,
        "commit_message_template": "Update metadata: {description}",
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name", "description", "creator", "dateCreated", "distribution"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1},
            },
        },
        "project_info": {
            "name": "test_project",
            "created_at": "2024-01-15T10:30:00Z",
            "biotope_version": "0.5.0",
            "last_modified": "2024-01-15T10:30:00Z",
            "builds": [],
            "knowledge_sources": [],
        },
        "registries": {
            "mcp": {
                "url": "https://biocontext.ai/registry.json",
                "cache_duration": 3600
            }
        },
    }
    
    config_file = config_dir / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    return tmp_path


@pytest.fixture
def biotope_project_without_mcp(tmp_path):
    """Create a biotope project without MCP registry configured."""
    # Create .biotope directory
    biotope_dir = tmp_path / ".biotope"
    biotope_dir.mkdir()
    
    # Create config directory
    config_dir = biotope_dir / "config"
    config_dir.mkdir()
    
    # Create config without MCP registry
    config = {
        "version": "1.0",
        "croissant_schema_version": "1.0",
        "default_metadata_template": "scientific",
        "data_storage": {"type": "local", "path": "data"},
        "checksum_algorithm": "sha256",
        "auto_stage": True,
        "commit_message_template": "Update metadata: {description}",
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": [
                "name", "description", "creator", "dateCreated", "distribution"
            ],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1},
            },
        },
        "project_info": {
            "name": "test_project",
            "created_at": "2024-01-15T10:30:00Z",
            "biotope_version": "0.5.0",
            "last_modified": "2024-01-15T10:30:00Z",
            "builds": [],
            "knowledge_sources": [],
        },
    }
    
    config_file = config_dir / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    return tmp_path


def test_get_mcp_status_with_accessible_registry(biotope_project_with_mcp):
    """Test MCP status when registry is accessible."""
    with patch("requests.get") as mock_get:
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = _get_mcp_status(biotope_project_with_mcp)
        
        assert result["configured"] is True
        assert "mcp" in result["registries"]
        assert result["registries"]["mcp"]["url"] == "https://biocontext.ai/registry.json"
        assert result["registries"]["mcp"]["accessible"] is True
        assert "Run 'biotope search <query>'" in result["suggestions"][0]


def test_get_mcp_status_with_unreachable_registry(biotope_project_with_mcp):
    """Test MCP status when registry is unreachable."""
    with patch("requests.get") as mock_get:
        # Mock failed response
        mock_get.side_effect = Exception("Network error")
        
        result = _get_mcp_status(biotope_project_with_mcp)
        
        assert result["configured"] is True
        assert "mcp" in result["registries"]
        assert result["registries"]["mcp"]["url"] == "https://biocontext.ai/registry.json"
        assert result["registries"]["mcp"]["accessible"] is False
        assert "Registry is unreachable" in result["suggestions"][0]


def test_get_mcp_status_without_registry(biotope_project_without_mcp):
    """Test MCP status when no registry is configured."""
    result = _get_mcp_status(biotope_project_without_mcp)
    
    assert result["configured"] is False
    assert result["registries"] == {}
    assert result["suggestions"] == []


def test_get_mcp_status_with_multiple_registries(biotope_project_with_mcp):
    """Test MCP status with multiple registries."""
    # Add another registry to the config
    config_file = biotope_project_with_mcp / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    
    config["registries"]["kg"] = {
        "url": "https://kg-registry.example.com/registry.json",
        "cache_duration": 3600
    }
    
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    with patch("requests.get") as mock_get:
        # Mock responses - mcp accessible, kg unreachable
        def mock_get_side_effect(url, **kwargs):
            mock_response = MagicMock()
            if "biocontext.ai" in url:
                mock_response.status_code = 200
            else:
                mock_response.status_code = 404
            return mock_response
        
        mock_get.side_effect = mock_get_side_effect
        
        result = _get_mcp_status(biotope_project_with_mcp)
        
        assert result["configured"] is True
        assert "mcp" in result["registries"]
        assert "kg" in result["registries"]
        assert result["registries"]["mcp"]["accessible"] is True
        assert result["registries"]["kg"]["accessible"] is False
        assert len(result["suggestions"]) == 1  # Should suggest search since one is accessible


def test_get_mcp_status_with_timeout():
    """Test MCP status with network timeout."""
    # Create a minimal project structure
    tmp_path = Path("/tmp/test_biotope")
    tmp_path.mkdir(exist_ok=True)
    config_dir = tmp_path / ".biotope" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config = {
        "registries": {
            "mcp": {
                "url": "https://biocontext.ai/registry.json",
                "cache_duration": 3600
            }
        }
    }
    
    config_file = config_dir / "biotope.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    with patch("requests.get") as mock_get:
        # Mock timeout
        mock_get.side_effect = Exception("Timeout")
        
        result = _get_mcp_status(tmp_path)
        
        assert result["configured"] is True
        assert result["registries"]["mcp"]["accessible"] is False
        assert "Registry is unreachable" in result["suggestions"][0]


def test_get_mcp_status_with_config_error(tmp_path):
    """Test MCP status when config loading fails."""
    # Don't create any config file
    
    result = _get_mcp_status(tmp_path)
    
    assert result["configured"] is False
    assert result["registries"] == {}
    assert result["suggestions"] == []


def test_get_mcp_status_with_empty_registries(biotope_project_without_mcp):
    """Test MCP status when registries section is empty."""
    # Add empty registries section
    config_file = biotope_project_without_mcp / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    
    config["registries"] = {}
    
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    result = _get_mcp_status(biotope_project_without_mcp)
    
    assert result["configured"] is False
    assert result["registries"] == {}
    assert result["suggestions"] == []


def test_get_mcp_status_with_malformed_registry_config(biotope_project_with_mcp):
    """Test MCP status with malformed registry configuration."""
    # Modify config to have malformed registry entry
    config_file = biotope_project_with_mcp / ".biotope" / "config" / "biotope.yaml"
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    
    config["registries"]["mcp"] = {
        "cache_duration": 3600
        # Missing URL
    }
    
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    with patch("requests.get") as mock_get:
        mock_get.side_effect = Exception("Network error")
        
        result = _get_mcp_status(biotope_project_with_mcp)
        
        assert result["configured"] is True
        assert "mcp" in result["registries"]
        assert result["registries"]["mcp"]["url"] == ""  # Empty URL
        assert result["registries"]["mcp"]["accessible"] is False 