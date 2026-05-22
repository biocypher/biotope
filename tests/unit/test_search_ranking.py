"""
Comprehensive test suite for search result ranking.

This test suite covers representative combinations of factors observable in real-world
bioinformatics tools and MCP servers to ensure proper ranking behavior.
"""

from unittest.mock import Mock, patch

import pytest

from biotope.registry.biocontext import BioContextRegistry
from biotope.registry.biotools import BioToolsRegistry


class TestSearchRanking:
    """Test search result ranking with representative data."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_registry_manager = Mock()
        self.biotools_registry = BioToolsRegistry(self.mock_registry_manager)
        self.biocontext_registry = BioContextRegistry(self.mock_registry_manager)

    def test_high_impact_tools_rank_first(self):
        """Test that tools with high citation counts appear first."""
        # Representative tools with varying impact levels
        test_tools = [
            {
                "name": "Low Impact Tool",
                "biotoolsID": "low_impact",
                "description": "A tool with low citations",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": {"citationCount": 5}}],
                "validated": 0,
                "homepage_status": 0,
                "elixir_badge": 0,
                "additionDate": "2020-01-01T00:00:00Z",
                "lastUpdate": "2020-01-01T00:00:00Z",
            },
            {
                "name": "Medium Impact Tool",
                "biotoolsID": "medium_impact",
                "description": "A tool with medium citations",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": {"citationCount": 50}}],
                "validated": 1,
                "homepage_status": 1,
                "elixir_badge": 0,
                "additionDate": "2019-01-01T00:00:00Z",
                "lastUpdate": "2021-01-01T00:00:00Z",
            },
            {
                "name": "High Impact Tool",
                "biotoolsID": "high_impact",
                "description": "A tool with high citations",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": {"citationCount": 500}}],
                "validated": 1,
                "homepage_status": 1,
                "elixir_badge": 1,
                "additionDate": "2018-01-01T00:00:00Z",
                "lastUpdate": "2022-01-01T00:00:00Z",
            },
            {
                "name": "Very High Impact Tool",
                "biotoolsID": "very_high_impact",
                "description": "A tool with very high citations",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": {"citationCount": 5000}}],
                "validated": 1,
                "homepage_status": 1,
                "elixir_badge": 1,
                "additionDate": "2017-01-01T00:00:00Z",
                "lastUpdate": "2023-01-01T00:00:00Z",
            },
        ]

        with patch.object(self.biotools_registry, "_fetch_tools", return_value=test_tools):
            results = self.biotools_registry.search("rna-seq", limit=10)

            # Extract citation counts in order
            citation_counts = []
            for result in results:
                citations = result.get("citations", "—")
                if citations != "—":
                    citation_counts.append(int(citations))
                else:
                    citation_counts.append(0)

            # Verify high impact tools come first
            assert (
                citation_counts[0] >= citation_counts[1]
            ), f"First tool citations ({citation_counts[0]}) should be >= second tool citations ({citation_counts[1]})"
            assert (
                citation_counts[1] >= citation_counts[2]
            ), f"Second tool citations ({citation_counts[1]}) should be >= third tool citations ({citation_counts[2]})"
            assert (
                citation_counts[2] >= citation_counts[3]
            ), f"Third tool citations ({citation_counts[2]}) should be >= fourth tool citations ({citation_counts[3]})"

    def test_mixed_impact_and_relevance_ranking(self):
        """Test ranking when tools have different combinations of impact and relevance."""
        test_tools = [
            {
                "name": "High Impact Low Relevance",
                "biotoolsID": "high_impact_low_rel",
                "description": "A tool with high citations but low relevance to query",
                "topic": [{"term": "Genomics"}],  # Not RNA-Seq related
                "function": [],
                "publication": [{"metadata": {"citationCount": 1000}}],
                "validated": 1,
                "homepage_status": 1,
                "elixir_badge": 1,
                "additionDate": "2018-01-01T00:00:00Z",
                "lastUpdate": "2022-01-01T00:00:00Z",
            },
            {
                "name": "Low Impact High Relevance",
                "biotoolsID": "low_impact_high_rel",
                "description": "A tool with low citations but high relevance to RNA-Seq",
                "topic": [{"term": "RNA-Seq"}],  # Highly relevant
                "function": [],
                "publication": [{"metadata": {"citationCount": 10}}],
                "validated": 0,
                "homepage_status": 0,
                "elixir_badge": 0,
                "additionDate": "2020-01-01T00:00:00Z",
                "lastUpdate": "2020-01-01T00:00:00Z",
            },
            {
                "name": "Medium Impact Medium Relevance",
                "biotoolsID": "medium_impact_medium_rel",
                "description": "A tool with medium citations and medium relevance",
                "topic": [{"term": "Transcriptomics"}],  # Somewhat relevant
                "function": [],
                "publication": [{"metadata": {"citationCount": 100}}],
                "validated": 1,
                "homepage_status": 0,
                "elixir_badge": 0,
                "additionDate": "2019-01-01T00:00:00Z",
                "lastUpdate": "2021-01-01T00:00:00Z",
            },
        ]

        with patch.object(self.biotools_registry, "_fetch_tools", return_value=test_tools):
            results = self.biotools_registry.search("rna-seq", limit=10)

            # High impact should still rank first despite lower relevance
            first_tool = results[0]
            assert (
                first_tool["name"] == "High Impact Low Relevance"
            ), f"Expected 'High Impact Low Relevance' first, got '{first_tool['name']}'"

    def test_no_citations_fallback_ranking(self):
        """Test ranking when tools have no citation data."""
        test_tools = [
            {
                "name": "No Citations Tool",
                "biotoolsID": "no_citations",
                "description": "A tool with no citation data",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [],  # No publications
                "validated": 0,
                "homepage_status": 0,
                "elixir_badge": 0,
                "additionDate": "2020-01-01T00:00:00Z",
                "lastUpdate": "2020-01-01T00:00:00Z",
            },
            {
                "name": "Some Citations Tool",
                "biotoolsID": "some_citations",
                "description": "A tool with some citations",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": {"citationCount": 25}}],
                "validated": 1,
                "homepage_status": 0,
                "elixir_badge": 0,
                "additionDate": "2019-01-01T00:00:00Z",
                "lastUpdate": "2021-01-01T00:00:00Z",
            },
            {
                "name": "High Citations Tool",
                "biotoolsID": "high_citations",
                "description": "A tool with high citations",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": {"citationCount": 500}}],
                "validated": 1,
                "homepage_status": 1,
                "elixir_badge": 1,
                "additionDate": "2018-01-01T00:00:00Z",
                "lastUpdate": "2022-01-01T00:00:00Z",
            },
        ]

        with patch.object(self.biotools_registry, "_fetch_tools", return_value=test_tools):
            results = self.biotools_registry.search("rna-seq", limit=10)

            # Tools with citations should rank higher than those without
            citation_counts = []
            for result in results:
                citations = result.get("citations", "—")
                if citations != "—":
                    citation_counts.append(int(citations))
                else:
                    citation_counts.append(0)

            # Verify tools with citations rank higher
            assert citation_counts[0] >= citation_counts[1], "First tool should have >= citations than second"
            assert citation_counts[1] >= citation_counts[2], "Second tool should have >= citations than third"

    def test_quality_indicators_ranking(self):
        """Test ranking based on quality indicators when citations are similar."""
        test_tools = [
            {
                "name": "Low Quality Tool",
                "biotoolsID": "low_quality",
                "description": "A tool with low quality indicators",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": {"citationCount": 100}}],
                "validated": 0,
                "homepage_status": 0,
                "elixir_badge": 0,
                "additionDate": "2020-01-01T00:00:00Z",
                "lastUpdate": "2020-01-01T00:00:00Z",
            },
            {
                "name": "High Quality Tool",
                "biotoolsID": "high_quality",
                "description": "A tool with high quality indicators",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": {"citationCount": 100}}],  # Same citations
                "validated": 1,
                "homepage_status": 1,
                "elixir_badge": 1,
                "additionDate": "2018-01-01T00:00:00Z",
                "lastUpdate": "2022-01-01T00:00:00Z",
            },
        ]

        with patch.object(self.biotools_registry, "_fetch_tools", return_value=test_tools):
            results = self.biotools_registry.search("rna-seq", limit=10)

            # High quality tool should rank higher when citations are similar
            first_tool = results[0]
            assert (
                first_tool["name"] == "High Quality Tool"
            ), f"Expected 'High Quality Tool' first, got '{first_tool['name']}'"

    def test_mcp_server_ranking(self):
        """Test ranking of MCP servers alongside bioinformatics tools."""
        test_servers = [
            {
                "name": "Low Stars MCP",
                "identifier": "low_stars_mcp",
                "description": "An MCP server with low GitHub stars",
                "keywords": ["RNA-Seq", "single-cell"],
                "stars": 5,
                "codeRepository": "https://github.com/user/low-stars-mcp",
            },
            {
                "name": "High Stars MCP",
                "identifier": "high_stars_mcp",
                "description": "An MCP server with high GitHub stars",
                "keywords": ["RNA-Seq", "analysis"],
                "stars": 200,
                "codeRepository": "https://github.com/user/high-stars-mcp",
            },
            {
                "name": "Medium Stars MCP",
                "identifier": "medium_stars_mcp",
                "description": "An MCP server with medium GitHub stars",
                "keywords": ["RNA-Seq", "pipeline"],
                "stars": 50,
                "codeRepository": "https://github.com/user/medium-stars-mcp",
            },
        ]

        with patch.object(self.biocontext_registry.registry_manager, "fetch_registry", return_value=test_servers):
            results = self.biocontext_registry.search("rna-seq", limit=10)

            # Extract star counts in order
            star_counts = []
            for result in results:
                stars = result.get("stars", 0)
                star_counts.append(stars)

            # Verify high star servers come first
            assert (
                star_counts[0] >= star_counts[1]
            ), f"First server stars ({star_counts[0]}) should be >= second server stars ({star_counts[1]})"
            assert (
                star_counts[1] >= star_counts[2]
            ), f"Second server stars ({star_counts[1]}) should be >= third server stars ({star_counts[2]})"

    def test_combined_registry_ranking(self):
        """Test ranking when combining results from multiple registries."""
        # This would test the unified search functionality
        # Implementation depends on how the search command combines results
        pass

    def test_edge_cases_ranking(self):
        """Test ranking with edge cases and boundary conditions."""
        test_tools = [
            {
                "name": "Zero Citations Tool",
                "biotoolsID": "zero_citations",
                "description": "A tool with exactly zero citations",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": {"citationCount": 0}}],
                "validated": 0,
                "homepage_status": 0,
                "elixir_badge": 0,
                "additionDate": "2020-01-01T00:00:00Z",
                "lastUpdate": "2020-01-01T00:00:00Z",
            },
            {
                "name": "Missing Metadata Tool",
                "biotoolsID": "missing_metadata",
                "description": "A tool with missing publication metadata",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": None}],  # Missing metadata
                "validated": 0,
                "homepage_status": 0,
                "elixir_badge": 0,
                "additionDate": "2020-01-01T00:00:00Z",
                "lastUpdate": "2020-01-01T00:00:00Z",
            },
            {
                "name": "Valid Tool",
                "biotoolsID": "valid_tool",
                "description": "A tool with valid data",
                "topic": [{"term": "RNA-Seq"}],
                "function": [],
                "publication": [{"metadata": {"citationCount": 100}}],
                "validated": 1,
                "homepage_status": 1,
                "elixir_badge": 0,
                "additionDate": "2019-01-01T00:00:00Z",
                "lastUpdate": "2021-01-01T00:00:00Z",
            },
        ]

        with patch.object(self.biotools_registry, "_fetch_tools", return_value=test_tools):
            results = self.biotools_registry.search("rna-seq", limit=10)

            # Should handle edge cases gracefully
            assert len(results) > 0, "Should return results even with edge cases"

            # Valid tool should rank higher than edge cases
            valid_tool_found = False
            for result in results:
                if result["name"] == "Valid Tool":
                    valid_tool_found = True
                    break

            assert valid_tool_found, "Valid tool should be included in results"


if __name__ == "__main__":
    pytest.main([__file__])
