"""Test search command functionality."""

from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from biotope.commands.search import search


@pytest.fixture
def biotope_project(tmp_path):
    """Create a mock biotope project structure."""
    # Create .git directory (required for find_biotope_root)
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    # Create .biotope directory
    biotope_dir = tmp_path / ".biotope"
    biotope_dir.mkdir()

    # Create config directory

    # Create datasets directory
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir()

    # Create cache directory
    cache_dir = biotope_dir / "cache"
    cache_dir.mkdir()

    # Create basic biotope config with registry settings
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
            "minimum_required_fields": ["name", "description", "creator", "dateCreated", "distribution"],
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
        "registries": {"mcp": {"url": "https://biocontext.ai/registry.json", "cache_duration": 3600}},
    }

    config_file = biotope_dir / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)

    return tmp_path


@pytest.fixture
def mock_registry_data():
    """Mock BioContext registry data."""
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


def test_search_command_success(biotope_project, mock_registry_data):
    """Test successful search command."""
    runner = CliRunner()

    with patch("biotope.registry.manager.RegistryManager.fetch_registry") as mock_fetch:
        mock_fetch.return_value = mock_registry_data

        # Change to the biotope project directory
        import os

        original_cwd = os.getcwd()
        os.chdir(biotope_project)

        try:
            result = runner.invoke(search, ["PubMed"])

            assert result.exit_code == 0
            assert "BioMCP" in result.output
            # Combined search now shows "All Resources" instead of just MCP servers
            assert "All Resources matching 'PubMed'" in result.output
            assert "Found 10 resource(s): 1 MCP server(s), 9 bioinformatics tool(s)" in result.output
        finally:
            os.chdir(original_cwd)


def test_search_command_no_results(biotope_project):
    """Test search with no results."""
    runner = CliRunner()

    with patch("biotope.registry.manager.RegistryManager.fetch_registry") as mock_fetch:
        mock_fetch.return_value = []

        # Change to the biotope project directory
        import os

        original_cwd = os.getcwd()
        os.chdir(biotope_project)

        try:
            result = runner.invoke(search, ["nonexistent"])

            assert result.exit_code == 0
            assert "No all resources found" in result.output
        finally:
            os.chdir(original_cwd)


def test_search_command_no_query(biotope_project):
    """Test search without query."""
    runner = CliRunner()

    result = runner.invoke(search, [])

    assert result.exit_code != 0
    assert "Usage: search [OPTIONS] [QUERY]" in result.output


def test_search_command_not_in_project(tmp_path):
    """Test search when not in a biotope project."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(search, ["PubMed"])

        assert result.exit_code != 0
        assert "Not in a biotope project" in result.output


def test_search_command_with_limit(biotope_project, mock_registry_data):
    """Test search with custom limit."""
    runner = CliRunner()

    with patch("biotope.registry.manager.RegistryManager.fetch_registry") as mock_fetch:
        mock_fetch.return_value = mock_registry_data

        # Change to the biotope project directory
        import os

        original_cwd = os.getcwd()
        os.chdir(biotope_project)

        try:
            result = runner.invoke(search, ["python", "--limit", "2"])

            assert result.exit_code == 0
            assert "Found 2 resource(s)" in result.output
        finally:
            os.chdir(original_cwd)


def test_search_command_with_type_option(biotope_project, mock_registry_data):
    """Test search with type option (should work but not affect results yet)."""
    runner = CliRunner()

    with patch("biotope.registry.manager.RegistryManager.fetch_registry") as mock_fetch:
        mock_fetch.return_value = mock_registry_data

        # Change to the biotope project directory
        import os

        original_cwd = os.getcwd()
        os.chdir(biotope_project)

        try:
            result = runner.invoke(search, ["PubMed", "--type", "mcp"])

            assert result.exit_code == 0
            assert "BioMCP" in result.output
        finally:
            os.chdir(original_cwd)


def test_search_command_network_error(biotope_project):
    """Test search with network error."""
    runner = CliRunner()

    # Mock both registry types to fail
    with patch("biotope.registry.biocontext.BioContextRegistry.search") as mock_mcp:
        with patch("biotope.registry.biotools.BioToolsRegistry.search") as mock_biotools:
            mock_mcp.side_effect = ValueError("Failed to fetch MCP registry")
            mock_biotools.side_effect = ValueError("Failed to fetch bio.tools registry")

            # Change to the biotope project directory
            import os

            original_cwd = os.getcwd()
            os.chdir(biotope_project)

            try:
                result = runner.invoke(search, ["PubMed"])

                # With combined search, the command should still succeed but show warnings
                assert result.exit_code == 0
                assert "No all resources found" in result.output
            finally:
                os.chdir(original_cwd)


def test_search_command_long_description_truncation(biotope_project):
    """Test that long descriptions are truncated in output."""
    long_description_data = [
        {
            "name": "Test MCP",
            "identifier": "test/mcp",
            "description": (
                "This is a very long description that should be truncated when displayed "
                "in the search results table. It contains more than 100 characters to test "
                "the truncation functionality."
            ),
            "keywords": ["test"],
        }
    ]

    runner = CliRunner()

    with patch("biotope.registry.manager.RegistryManager.fetch_registry") as mock_fetch:
        mock_fetch.return_value = long_description_data

        # Change to the biotope project directory
        import os

        original_cwd = os.getcwd()
        os.chdir(biotope_project)

        try:
            result = runner.invoke(search, ["test"])

            assert result.exit_code == 0
            assert "Test MCP" in result.output
            assert "..." in result.output  # Should be truncated
        finally:
            os.chdir(original_cwd)


def test_search_command_table_formatting(biotope_project, mock_registry_data):
    """Test that search results are properly formatted in table."""
    runner = CliRunner()

    with patch("biotope.registry.manager.RegistryManager.fetch_registry") as mock_fetch:
        mock_fetch.return_value = mock_registry_data

        # Change to the biotope project directory
        import os

        original_cwd = os.getcwd()
        os.chdir(biotope_project)

        try:
            result = runner.invoke(search, ["python"])

            assert result.exit_code == 0
            # Check that table headers are present
            assert "Name" in result.output
            assert "Identifier" in result.output
            assert "Description" in result.output
            assert "Keywords" in result.output
            assert "Impact" in result.output  # New column for combined search
            # Check that data is present
            assert "BioMCP" in result.output
            assert "AACT MCP" in result.output
        finally:
            os.chdir(original_cwd)


def test_search_command_sort_by_stars(biotope_project, mock_registry_data):
    """Test search with sorting by stars."""
    runner = CliRunner()

    with patch("biotope.registry.manager.RegistryManager.fetch_registry") as mock_fetch:
        mock_fetch.return_value = mock_registry_data

        # Change to the biotope project directory
        import os

        original_cwd = os.getcwd()
        os.chdir(biotope_project)

        try:
            result = runner.invoke(search, ["python", "--sort", "impact"])

            assert result.exit_code == 0
            assert "Impact" in result.output
            # Should show star counts (even if they're "—" for mocked data)
        finally:
            os.chdir(original_cwd)


def test_search_command_sort_by_name(biotope_project, mock_registry_data):
    """Test search with sorting by name."""
    runner = CliRunner()

    with patch("biotope.registry.manager.RegistryManager.fetch_registry") as mock_fetch:
        mock_fetch.return_value = mock_registry_data

        # Change to the biotope project directory
        import os

        original_cwd = os.getcwd()
        os.chdir(biotope_project)

        try:
            result = runner.invoke(search, ["python", "--sort", "name"])

            assert result.exit_code == 0
            assert "AACT MCP" in result.output
            assert "BioMCP" in result.output
        finally:
            os.chdir(original_cwd)


def test_search_command_invalid_sort_option(biotope_project):
    """Test search with invalid sort option."""
    runner = CliRunner()

    # Change to the biotope project directory
    import os

    original_cwd = os.getcwd()
    os.chdir(biotope_project)

    try:
        result = runner.invoke(search, ["test", "--sort", "invalid"])

        assert result.exit_code != 0
        # Should show error about invalid choice
    finally:
        os.chdir(original_cwd)
