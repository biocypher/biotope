"""Test registry functionality."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from biotope.registry.biocontext import BioContextRegistry
from biotope.registry.biotools import BioToolsRegistry
from biotope.registry.manager import RegistryManager


@pytest.fixture
def mock_registry_data():
    """Mock registry data."""
    return [
        {
            "name": "Test Server 1",
            "identifier": "test/server1",
            "description": "Test server 1",
            "keywords": ["test", "python"],
        },
        {
            "name": "Test Server 2",
            "identifier": "test/server2",
            "description": "Test server 2",
            "keywords": ["test", "python"],
        },
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
            "codeRepository": "https://github.com/genomoncology/biomcp",
        },
        {
            "name": "AACT MCP",
            "identifier": "navisbio/AACT_MCP",
            "description": "Clinical trials data access",
            "keywords": ["AACT", "python"],
            "codeRepository": "https://github.com/navisbio/AACT_MCP",
        },
        {
            "name": "Reactome MCP",
            "identifier": "augmented-nature/reactome-mcp",
            "description": "Pathway data access",
            "keywords": ["Reactome", "pathways"],
            "codeRepository": "https://github.com/augmented-nature/reactome-mcp",
        },
    ]


def test_registry_manager_initialization(tmp_path):
    """Test RegistryManager initialization."""
    registry_manager = RegistryManager(tmp_path)

    assert registry_manager.biotope_root == tmp_path
    assert registry_manager.cache_dir == tmp_path / ".biotope" / "cache"
    assert registry_manager.cache_dir.exists()


@patch("biotope.registry.manager.requests.get")
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


@patch("biotope.registry.manager.requests.get")
def test_registry_manager_fetch_registry_error(mock_get, tmp_path):
    """Test RegistryManager.fetch_registry with network error."""
    # Mock failed response
    mock_get.side_effect = requests.RequestException("Network error")

    registry_manager = RegistryManager(tmp_path)

    with pytest.raises(ValueError, match="Failed to fetch registry"):
        registry_manager.fetch_registry("https://biocontext.ai/registry.json")


def test_registry_manager_caching(tmp_path, mock_registry_data):
    """Test RegistryManager caching functionality."""
    import hashlib

    registry_manager = RegistryManager(tmp_path)

    # Create a cached file using the same hash algorithm as the manager
    url = "https://biocontext.ai/registry.json"
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_file = registry_manager.cache_dir / f"registry_{cache_key}.json"
    with open(cache_file, "w") as f:
        json.dump(mock_registry_data, f)

    # Should return cached data without making HTTP request
    with patch("biotope.registry.manager.requests.get") as mock_get:
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

    with patch.object(registry_manager, "fetch_registry", return_value=mock_registry_data):
        results = biocontext.search("test")

        assert len(results) == 2
        assert all("test" in server["name"].lower() or "test" in server["description"].lower() for server in results)


def test_biocontext_search_no_results(tmp_path, mock_registry_data):
    """Test BioContextRegistry.search with no matching results."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch.object(registry_manager, "fetch_registry", return_value=mock_registry_data):
        results = biocontext.search("nonexistent")

        assert len(results) == 0


def test_biocontext_search_limit(tmp_path, mock_registry_data):
    """Test BioContextRegistry.search with limit."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch.object(registry_manager, "fetch_registry", return_value=mock_registry_data):
        results = biocontext.search("test", limit=1)

        assert len(results) == 1


def test_biocontext_get_server(tmp_path, mock_registry_data):
    """Test BioContextRegistry.get_server method."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch.object(registry_manager, "fetch_registry", return_value=mock_registry_data):
        server = biocontext.get_server("test/server1")

        assert server is not None
        assert server["name"] == "Test Server 1"


def test_biocontext_get_server_not_found(tmp_path, mock_registry_data):
    """Test BioContextRegistry.get_server with non-existent server."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch.object(registry_manager, "fetch_registry", return_value=mock_registry_data):
        server = biocontext.get_server("nonexistent/server")

        assert server is None


def test_biocontext_search_case_insensitive(tmp_path, mock_registry_data):
    """Test BioContextRegistry.search is case insensitive."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch.object(registry_manager, "fetch_registry", return_value=mock_registry_data):
        results_lower = biocontext.search("test")
        results_upper = biocontext.search("TEST")

        assert len(results_lower) == len(results_upper)


def test_biocontext_search_with_stars(tmp_path, mock_registry_data_with_repos):
    """Test BioContextRegistry.search with star count fetching."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch.object(registry_manager, "fetch_registry", return_value=mock_registry_data_with_repos):
        with patch.object(biocontext, "_get_github_stars", return_value=100):
            results = biocontext.search("python")

            assert len(results) > 0
            for server in results:
                assert "stars" in server
                assert server["stars"] == 100


def test_biocontext_search_with_stars_failure(tmp_path, mock_registry_data_with_repos):
    """Test BioContextRegistry.search when star fetching fails."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch.object(registry_manager, "fetch_registry", return_value=mock_registry_data_with_repos):
        with patch.object(biocontext, "_get_github_stars", return_value=None):
            results = biocontext.search("python")

            assert len(results) > 0
            for server in results:
                assert "stars" in server
                assert server["stars"] == "—"


def test_biocontext_search_sort_by_stars(tmp_path, mock_registry_data_with_repos):
    """Test BioContextRegistry.search with sorting by stars."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch.object(registry_manager, "fetch_registry", return_value=mock_registry_data_with_repos):
        with patch.object(biocontext, "_get_github_stars", side_effect=[100, 50, 200]):
            results = biocontext.search("MCP", sort="impact")  # "MCP" matches all servers

            # Should be sorted by stars (descending)
            assert len(results) == 3
            # First result should have highest star count
            assert results[0]["stars"] == 200


def test_biocontext_search_sort_by_name(tmp_path, mock_registry_data_with_repos):
    """Test BioContextRegistry.search with sorting by name."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch.object(registry_manager, "fetch_registry", return_value=mock_registry_data_with_repos):
        with patch.object(biocontext, "_get_github_stars", return_value=100):
            results = biocontext.search("python", sort="name")

            # Should be sorted alphabetically by name
            assert len(results) > 0
            names = [server["name"] for server in results]
            assert names == sorted(names)


def test_biocontext_calculate_relevance_score(tmp_path):
    """Test relevance score calculation."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    # Test server with exact name match
    server_exact_name = {
        "name": "Python MCP Server",
        "description": "A server for Python",
        "keywords": ["python", "mcp"],
        "stars": 100,
    }
    score_exact = biocontext._calculate_relevance_score(server_exact_name, "python")
    assert score_exact >= 10.0  # Exact name match

    # Test server with keyword match only
    server_keyword_only = {
        "name": "BioMCP",
        "description": "A bioinformatics server",
        "keywords": ["python", "bioinformatics"],
        "stars": 50,
    }
    score_keyword = biocontext._calculate_relevance_score(server_keyword_only, "python")
    assert score_keyword >= 2.0  # Keyword match (exact keyword = 2.0 points)
    assert score_keyword < score_exact  # Should be lower than exact name match

    # Test server with no matches
    server_no_match = {
        "name": "Reactome MCP",
        "description": "A pathway server",
        "keywords": ["reactome", "pathways"],
        "stars": 25,
    }
    score_no_match = biocontext._calculate_relevance_score(server_no_match, "python")
    assert score_no_match < 2.0  # Only star bonus


def test_biocontext_get_github_stars_success(tmp_path):
    """Test BioContextRegistry._get_github_stars with successful API call."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch("requests.get") as mock_get:
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

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        stars = biocontext._get_github_stars("https://github.com/test/repo")

        assert stars is None


def test_biocontext_get_github_token_from_env(tmp_path):
    """Test GitHub token retrieval from environment variable."""
    registry_manager = RegistryManager(tmp_path)
    biocontext = BioContextRegistry(registry_manager)

    with patch.dict("os.environ", {"GITHUB_TOKEN": "test_token"}):
        token = biocontext._get_github_token()
        assert token == "test_token"


def test_biotools_registry_initialization(tmp_path):
    """Test BioToolsRegistry initialization."""
    registry_manager = RegistryManager(tmp_path)
    biotools = BioToolsRegistry(registry_manager)

    assert biotools.registry_manager == registry_manager
    assert biotools.base_url == "https://bio.tools/api"


def test_biotools_registry_initialization_custom_url(tmp_path):
    """Test BioToolsRegistry initialization with custom URL."""
    registry_manager = RegistryManager(tmp_path)
    custom_url = "https://custom-biotools.example.com/api"
    biotools = BioToolsRegistry(registry_manager, custom_url)

    assert biotools.base_url == custom_url


def test_biotools_search(tmp_path):
    """Test BioToolsRegistry.search method."""
    registry_manager = RegistryManager(tmp_path)
    biotools = BioToolsRegistry(registry_manager)

    mock_tools_data = [
        {
            "name": "BLAST",
            "biotoolsID": "blast",
            "description": "Basic Local Alignment Search Tool",
            "topic": [{"term": "Sequence analysis"}],
            "function": [{"name": "Sequence alignment"}],
        },
        {
            "name": "ClustalW",
            "biotoolsID": "clustalw",
            "description": "Multiple sequence alignment tool",
            "topic": [{"term": "Sequence analysis"}],
            "function": [{"name": "Multiple alignment"}],
        },
    ]

    with patch.object(biotools, "_fetch_tools", return_value=mock_tools_data):
        results = biotools.search("sequence")

        assert len(results) == 2
        # Both tools should match "sequence" in their descriptions
        assert any("sequence" in tool["name"].lower() or "sequence" in tool["description"].lower() for tool in results)


def test_biotools_search_no_results(tmp_path):
    """Test BioToolsRegistry.search with no matching results."""
    registry_manager = RegistryManager(tmp_path)
    biotools = BioToolsRegistry(registry_manager)

    with patch.object(biotools, "_fetch_tools", return_value=[]):
        results = biotools.search("nonexistent")

        assert len(results) == 0


def test_biotools_search_limit(tmp_path):
    """Test BioToolsRegistry.search with limit."""
    registry_manager = RegistryManager(tmp_path)
    biotools = BioToolsRegistry(registry_manager)

    mock_tools_data = [{"name": f"Tool{i}", "biotoolsID": f"tool{i}", "description": f"Tool {i}"} for i in range(5)]

    with patch.object(biotools, "_fetch_tools", return_value=mock_tools_data):
        results = biotools.search("tool", limit=3)

        assert len(results) == 3


def test_biotools_get_tool(tmp_path):
    """Test BioToolsRegistry.get_tool method."""
    registry_manager = RegistryManager(tmp_path)
    biotools = BioToolsRegistry(registry_manager)

    mock_tool_data = {"name": "BLAST", "biotoolsID": "blast", "description": "Basic Local Alignment Search Tool"}

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_tool_data
        mock_get.return_value = mock_response

        tool = biotools.get_tool("blast")

        assert tool is not None
        assert tool["name"] == "BLAST"
        assert tool["biotoolsID"] == "blast"


def test_biotools_get_tool_not_found(tmp_path):
    """Test BioToolsRegistry.get_tool with non-existent tool."""
    registry_manager = RegistryManager(tmp_path)
    biotools = BioToolsRegistry(registry_manager)

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        tool = biotools.get_tool("nonexistent")

        assert tool is None


def test_biotools_calculate_relevance_score(tmp_path):
    """Test relevance score calculation for bio.tools."""
    registry_manager = RegistryManager(tmp_path)
    biotools = BioToolsRegistry(registry_manager)

    # Test tool with exact name match
    tool_exact_name = {
        "name": "Sequence Alignment Tool",
        "description": "A tool for sequence alignment",
        "topic": [{"term": "Sequence analysis"}],
        "function": [{"name": "Alignment"}],
    }
    score_exact = biotools._calculate_relevance_score(tool_exact_name, "sequence")
    assert score_exact >= 9.0  # Exact name match (5.0) + description (2.5) + topic (2.0) + function (1.5) = 11.0

    # Test tool with topic match only
    tool_topic_only = {
        "name": "BLAST",
        "description": "A bioinformatics tool",
        "topic": [{"term": "Sequence analysis"}],
        "function": [{"name": "Database search"}],
    }
    score_topic = biotools._calculate_relevance_score(tool_topic_only, "sequence")
    assert score_topic >= 2.0  # Topic match (2.0 points for exact topic match)
    assert score_topic < score_exact  # Should be lower than exact name match


def test_biotools_format_tool_for_display(tmp_path):
    """Test tool formatting for display."""
    registry_manager = RegistryManager(tmp_path)
    biotools = BioToolsRegistry(registry_manager)

    mock_tool = {
        "name": "BLAST",
        "biotoolsID": "blast",
        "description": "Basic Local Alignment Search Tool",
        "topic": [{"term": "Sequence analysis"}, {"term": "Database search"}],
        "function": [{"name": "Sequence alignment"}, {"name": "Database search"}],
        "homepage": "https://blast.ncbi.nlm.nih.gov/",
    }

    formatted = biotools._format_tool_for_display(mock_tool)

    assert formatted["name"] == "BLAST"
    assert formatted["identifier"] == "blast"
    assert formatted["description"] == "Basic Local Alignment Search Tool"
    assert "Sequence analysis" in formatted["keywords"]
    assert "Database search" in formatted["keywords"]
    assert "Sequence alignment" in formatted["keywords"]
    assert formatted["homepage"] == "https://blast.ncbi.nlm.nih.gov/"
    assert formatted["citations"] == "—"  # bio.tools doesn't have citations for this mock
