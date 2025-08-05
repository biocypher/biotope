"""Test registry functionality."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import requests

from biotope.registry.manager import RegistryManager
from biotope.registry.biocontext import BioContextRegistry


@pytest.fixture
def mock_registry_data():
    """Mock registry data."""
    return [
        {
            "name": "Test Server 1",
            "identifier": "test/server1",
            "description": "Test server 1",
            "keywords": ["test", "python"]
        },
        {
            "name": "Test Server 2",
            "identifier": "test/server2",
            "description": "Test server 2",
            "keywords": ["test", "python"]
        }
    ]


@pytest.fixture
def mock_registry_data_with_repos():
    """Mock registry data with GitHub repositories."""
    return [
        {
            "name": "BioMCP",
            "identifier": "genomoncology/biomcp",
            "description": "A Model Context Protocol server for bioinformatics",
            "keywords": ["PubMed", "ClinicalTrials", "MyVariant", "python"],
            "codeRepository": "https://github.com/genomoncology/biomcp"
        },
        {
            "name": "AACT MCP",
            "identifier": "navisbio/AACT_MCP",
            "description": "Clinical trials data access",
            "keywords": ["AACT", "python"],
            "codeRepository": "https://github.com/navisbio/AACT_MCP"
        },
        {
            "name": "Reactome MCP",
            "identifier": "augmented-nature/reactome-mcp",
            "description": "Pathway data access",
            "keywords": ["Reactome", "pathways"],
            "codeRepository": "https://github.com/augmented-nature/reactome-mcp"
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
    
    # Create a cached file
    cache_file = registry_manager.cache_dir / f"registry_{hash('https://biocontext.ai/registry.json')}.json"
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


def test_biocontext_registry_initialization_custom_url(tmp_path):
    """Test BioContextRegistry initialization with custom URL."""
    registry_manager = RegistryManager(tmp_path)
    custom_url = "https://custom-registry.example.com/registry.json"
    biocontext = BioContextRegistry(registry_manager, custom_url)
    
    assert biocontext.url == custom_url


def test_biocontext_search(tmp_path, mock_registry_data):
    """Test BioContextRegistry.search method."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data):
        results = biocontext.search("test")
        
        assert len(results) == 2
        assert all("test" in server["name"].lower() or "test" in server["description"].lower() 
                  for server in results)


def test_biocontext_search_no_results(tmp_path, mock_registry_data):
    """Test BioContextRegistry.search with no matching results."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data):
        results = biocontext.search("nonexistent")
        
        assert len(results) == 0


def test_biocontext_search_limit(tmp_path, mock_registry_data):
    """Test BioContextRegistry.search with limit."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data):
        results = biocontext.search("test", limit=1)
        
        assert len(results) == 1


def test_biocontext_get_server(tmp_path, mock_registry_data):
    """Test BioContextRegistry.get_server method."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data):
        server = biocontext.get_server("test/server1")
        
        assert server is not None
        assert server["name"] == "Test Server 1"


def test_biocontext_get_server_not_found(tmp_path, mock_registry_data):
    """Test BioContextRegistry.get_server with non-existent server."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data):
        server = biocontext.get_server("nonexistent/server")
        
        assert server is None


def test_biocontext_search_case_insensitive(tmp_path, mock_registry_data):
    """Test BioContextRegistry.search is case insensitive."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data):
        results_lower = biocontext.search("test")
        results_upper = biocontext.search("TEST")
        
        assert len(results_lower) == len(results_upper)


def test_biocontext_search_with_stars(tmp_path, mock_registry_data_with_repos):
    """Test BioContextRegistry.search with star count fetching."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data_with_repos):
        with patch.object(biocontext, '_get_github_stars', return_value=100):
            results = biocontext.search("python")
            
            assert len(results) > 0
            for server in results:
                assert "stars" in server
                assert server["stars"] == 100


def test_biocontext_search_with_stars_failure(tmp_path, mock_registry_data_with_repos):
    """Test BioContextRegistry.search when star fetching fails."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data_with_repos):
        with patch.object(biocontext, '_get_github_stars', return_value=None):
            results = biocontext.search("python")
            
            assert len(results) > 0
            for server in results:
                assert "stars" in server
                assert server["stars"] == "—"


def test_biocontext_search_sort_by_stars(tmp_path, mock_registry_data_with_repos):
    """Test BioContextRegistry.search with sorting by stars."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data_with_repos):
        with patch.object(biocontext, '_get_github_stars', side_effect=[100, 50, 200]):
            results = biocontext.search("MCP", sort="stars")  # "MCP" matches all servers
            
            # Should be sorted by stars (descending)
            assert len(results) == 3
            # First result should have highest star count
            assert results[0]["stars"] == 200


def test_biocontext_search_sort_by_name(tmp_path, mock_registry_data_with_repos):
    """Test BioContextRegistry.search with sorting by name."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data_with_repos):
        with patch.object(biocontext, '_get_github_stars', return_value=100):
            results = biocontext.search("python", sort="name")
            
            # Should be sorted alphabetically by name
            assert len(results) > 0
            names = [server["name"] for server in results]
            assert names == sorted(names)


def test_biocontext_search_sort_relevance(tmp_path, mock_registry_data_with_repos):
    """Test BioContextRegistry.search with relevance sorting (default)."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch.object(registry_manager, 'fetch_registry', return_value=mock_registry_data_with_repos):
        with patch.object(biocontext, '_get_github_stars', return_value=100):
            results = biocontext.search("python", sort="relevance")
            
            # Should maintain original order (most relevant first)
            assert len(results) > 0


def test_biocontext_get_github_stars_success(tmp_path):
    """Test BioContextRegistry._get_github_stars with successful API call."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"stargazers_count": 150}
        mock_get.return_value = mock_response
        
        stars = biocontext._get_github_stars("https://github.com/test/repo")
        
        assert stars == 150


def test_biocontext_get_github_stars_api_error(tmp_path):
    """Test BioContextRegistry._get_github_stars with API error."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        stars = biocontext._get_github_stars("https://github.com/test/repo")
        
        assert stars is None


def test_biocontext_get_github_stars_network_error(tmp_path):
    """Test BioContextRegistry._get_github_stars with network error."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.RequestException("Network error")
        
        stars = biocontext._get_github_stars("https://github.com/test/repo")
        
        assert stars is None


def test_biocontext_get_github_stars_invalid_url(tmp_path):
    """Test BioContextRegistry._get_github_stars with invalid GitHub URL."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    stars = biocontext._get_github_stars("https://not-github.com/test/repo")
    
    assert stars is None


def test_biocontext_get_github_stars_malformed_url(tmp_path):
    """Test BioContextRegistry._get_github_stars with malformed GitHub URL."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)
    
    stars = biocontext._get_github_stars("https://github.com/invalid")
    
    assert stars is None 