"""Unit tests for registry infrastructure."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import requests

from biotope.registry.manager import RegistryManager
from biotope.registry.biocontext import BioContextRegistry


@pytest.fixture
def mock_registry_data():
    """Mock BioContext registry data."""
    return [
        {
            "name": "BioMCP",
            "identifier": "genomoncology/biomcp",
            "description": "A Model Context Protocol server for bioinformatics",
            "keywords": ["PubMed", "ClinicalTrials", "MyVariant", "python"]
        },
        {
            "name": "AACT MCP",
            "identifier": "navisbio/AACT_MCP",
            "description": "Clinical trials data access",
            "keywords": ["AACT", "python"]
        },
        {
            "name": "Reactome MCP",
            "identifier": "augmented-nature/reactome-mcp",
            "description": "Pathway data access",
            "keywords": ["Reactome", "pathways"]
        }
    ]


def test_registry_manager_initialization(tmp_path):
    """Test RegistryManager initialization."""
    registry_manager = RegistryManager(tmp_path)
    
    assert registry_manager.biotope_root == tmp_path
    assert registry_manager.cache_dir == tmp_path / ".biotope" / "cache"
    assert registry_manager.cache_dir.exists()


@patch('biotope.registry.manager.requests.get')
def test_registry_manager_fetch_registry(mock_get, tmp_path, mock_registry_data):
    """Test RegistryManager.fetch_registry method."""
    # Mock successful response
    mock_response = MagicMock()
    mock_response.json.return_value = mock_registry_data
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    registry_manager = RegistryManager(tmp_path)
    result = registry_manager.fetch_registry("https://biocontext.ai/registry.json")
    
    assert result == mock_registry_data
    mock_get.assert_called_once_with("https://biocontext.ai/registry.json", timeout=10)


@patch('biotope.registry.manager.requests.get')
def test_registry_manager_fetch_registry_error(mock_get, tmp_path):
    """Test RegistryManager.fetch_registry with network error."""
    # Mock failed response
    mock_get.side_effect = requests.RequestException("Network error")
    
    registry_manager = RegistryManager(tmp_path)
    
    with pytest.raises(ValueError, match="Failed to fetch registry"):
        registry_manager.fetch_registry("https://biocontext.ai/registry.json")


def test_registry_manager_caching(tmp_path, mock_registry_data):
    """Test RegistryManager caching functionality."""
    registry_manager = RegistryManager(tmp_path)
    cache_file = registry_manager.cache_dir / f"registry_{hash('https://biocontext.ai/registry.json')}.json"
    
    # Write mock data to cache
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(mock_registry_data, f)
    
    # Should return cached data without making HTTP request
    with patch('biotope.registry.manager.requests.get') as mock_get:
        result = registry_manager.fetch_registry("https://biocontext.ai/registry.json")
        
        assert result == mock_registry_data
        mock_get.assert_not_called()


def test_biocontext_registry_initialization(tmp_path):
    """Test BioContextRegistry initialization."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    assert biocontext.registry_manager == registry_manager
    assert biocontext.url == "https://biocontext.ai/registry.json"


@patch('biotope.registry.RegistryManager.fetch_registry')
def test_biocontext_search(mock_fetch, tmp_path, mock_registry_data):
    """Test BioContextRegistry.search method."""
    mock_fetch.return_value = mock_registry_data
    
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    # Search for PubMed servers
    results = biocontext.search("PubMed", limit=5)
    
    assert len(results) == 1
    assert results[0]["name"] == "BioMCP"
    assert results[0]["identifier"] == "genomoncology/biomcp"


@patch('biotope.registry.RegistryManager.fetch_registry')
def test_biocontext_search_no_results(mock_fetch, tmp_path, mock_registry_data):
    """Test BioContextRegistry.search with no matching results."""
    mock_fetch.return_value = mock_registry_data
    
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    # Search for non-existent term
    results = biocontext.search("nonexistent", limit=5)
    
    assert len(results) == 0


@patch('biotope.registry.RegistryManager.fetch_registry')
def test_biocontext_search_limit(mock_fetch, tmp_path, mock_registry_data):
    """Test BioContextRegistry.search with limit."""
    mock_fetch.return_value = mock_registry_data
    
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    # Search with limit of 1
    results = biocontext.search("python", limit=1)
    
    assert len(results) == 1


@patch('biotope.registry.RegistryManager.fetch_registry')
def test_biocontext_get_server(mock_fetch, tmp_path, mock_registry_data):
    """Test BioContextRegistry.get_server method."""
    mock_fetch.return_value = mock_registry_data
    
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    # Get specific server
    server = biocontext.get_server("genomoncology/biomcp")
    
    assert server is not None
    assert server["name"] == "BioMCP"
    assert server["identifier"] == "genomoncology/biomcp"


@patch('biotope.registry.RegistryManager.fetch_registry')
def test_biocontext_get_server_not_found(mock_fetch, tmp_path, mock_registry_data):
    """Test BioContextRegistry.get_server with non-existent identifier."""
    mock_fetch.return_value = mock_registry_data
    
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    # Get non-existent server
    server = biocontext.get_server("nonexistent/server")
    
    assert server is None


@patch('biotope.registry.RegistryManager.fetch_registry')
def test_biocontext_search_case_insensitive(mock_fetch, tmp_path, mock_registry_data):
    """Test BioContextRegistry.search is case insensitive."""
    mock_fetch.return_value = mock_registry_data
    
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    # Search with different cases
    results_lower = biocontext.search("pubmed", limit=5)
    results_upper = biocontext.search("PUBMED", limit=5)
    results_mixed = biocontext.search("PubMed", limit=5)
    
    assert len(results_lower) == len(results_upper) == len(results_mixed) == 1
    assert results_lower[0]["identifier"] == results_upper[0]["identifier"] == results_mixed[0]["identifier"] 