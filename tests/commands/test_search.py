"""CLI smoke tests for biotope search."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from biotope.commands.search import search


@pytest.fixture
def runner():
    return CliRunner()


def _mock_biotools_results():
    return [
        {
            "name": "Tool A",
            "identifier": "tool_a",
            "description": "bioinformatics tool",
            "keywords": ["python"],
            "_registry_type": "biotools",
            "_registry_name": "Bioinformatics Tool",
            "citations": "10",
        },
    ]


def _mock_mcp_results(mock_registry_data):
    return [
        {**item, "_registry_type": "mcp", "_registry_name": "MCP Server", "stars": "—"}
        for item in mock_registry_data
        if "PubMed" in item.get("keywords", []) or "PubMed" in item.get("description", "")
    ] or [
        {
            **mock_registry_data[0],
            "_registry_type": "mcp",
            "_registry_name": "MCP Server",
            "stars": "—",
        },
    ]


def test_search_combined_success(runner, biotope_project_with_registry, mock_mcp_registry_data):
    with (
        patch("biotope.registry.biocontext.BioContextRegistry.search") as mock_mcp,
        patch("biotope.registry.biotools.BioToolsRegistry.search") as mock_biotools,
        runner.isolated_filesystem(temp_dir=biotope_project_with_registry),
    ):
        mock_mcp.return_value = _mock_mcp_results(mock_mcp_registry_data)
        mock_biotools.return_value = _mock_biotools_results()
        result = runner.invoke(search, ["PubMed"])
    assert result.exit_code == 0
    assert "BioMCP" in result.output
    assert "All Resources matching 'PubMed'" in result.output
    assert "Found 2 resource(s)" in result.output


def test_search_mcp_only(runner, biotope_project_with_registry, mock_mcp_registry_data):
    with (
        patch("biotope.registry.biocontext.BioContextRegistry.search", return_value=mock_mcp_registry_data),
        runner.isolated_filesystem(temp_dir=biotope_project_with_registry),
    ):
        result = runner.invoke(search, ["PubMed", "--type", "mcp"])
    assert result.exit_code == 0
    assert "BioMCP" in result.output
    assert "MCP Servers matching" in result.output


def test_search_no_results(runner, biotope_project_with_registry):
    with (
        patch("biotope.registry.biocontext.BioContextRegistry.search", return_value=[]),
        patch("biotope.registry.biotools.BioToolsRegistry.search", return_value=[]),
        runner.isolated_filesystem(temp_dir=biotope_project_with_registry),
    ):
        result = runner.invoke(search, ["nonexistent"])
    assert result.exit_code == 0
    assert "No all resources found" in result.output


def test_search_no_query(runner):
    result = runner.invoke(search, [])
    assert result.exit_code != 0


def test_search_not_in_project(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(search, ["PubMed"])
    assert result.exit_code != 0
    assert "Not in a biotope project" in result.output


def test_search_with_limit(runner, biotope_project_with_registry, mock_mcp_registry_data):
    with (
        patch("biotope.registry.biocontext.BioContextRegistry.search") as mock_mcp,
        patch("biotope.registry.biotools.BioToolsRegistry.search") as mock_biotools,
        runner.isolated_filesystem(temp_dir=biotope_project_with_registry),
    ):
        mock_mcp.return_value = mock_mcp_registry_data
        mock_biotools.return_value = _mock_biotools_results()
        result = runner.invoke(search, ["python", "--limit", "2"])
    assert result.exit_code == 0
    assert "Found 2 resource(s)" in result.output


def test_search_invalid_sort(runner, biotope_project_with_registry):
    with runner.isolated_filesystem(temp_dir=biotope_project_with_registry):
        result = runner.invoke(search, ["test", "--sort", "invalid"])
    assert result.exit_code != 0
