"""Search ranking behavior for registry classes."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from biotope.registry.biocontext import BioContextRegistry
from biotope.registry.biotools import BioToolsRegistry


def _biotools_tool(name: str, citations: int, **extra) -> dict:
    return {
        "name": name,
        "biotoolsID": name.lower().replace(" ", "_"),
        "description": extra.get("description", f"Tool {name}"),
        "topic": [{"term": extra.get("topic", "RNA-Seq")}],
        "function": [],
        "publication": [{"metadata": {"citationCount": citations}}],
        "validated": extra.get("validated", 0),
        "homepage_status": extra.get("homepage_status", 0),
        "elixir_badge": extra.get("elixir_badge", 0),
        "additionDate": "2020-01-01T00:00:00Z",
        "lastUpdate": "2020-01-01T00:00:00Z",
    }


@pytest.fixture
def biotools_registry():
    return BioToolsRegistry(Mock())


@pytest.fixture
def biocontext_registry():
    return BioContextRegistry(Mock())


def _citation_order(results: list[dict]) -> list[int]:
    order = []
    for result in results:
        citations = result.get("citations", "—")
        order.append(int(citations) if citations != "—" else 0)
    return order


@pytest.mark.parametrize(
    "tools",
    [
        [
            _biotools_tool("Low", 5),
            _biotools_tool("Medium", 50),
            _biotools_tool("High", 500),
            _biotools_tool("Very High", 5000),
        ],
        [
            _biotools_tool("No Citations", 0, publication=[]),
            _biotools_tool("Some", 25),
            _biotools_tool("High", 500),
        ],
    ],
)
def test_biotools_results_sorted_by_impact(biotools_registry, tools):
    with patch.object(biotools_registry, "_fetch_tools", return_value=tools):
        results = biotools_registry.search("rna-seq", limit=10)
    counts = _citation_order(results)
    assert counts == sorted(counts, reverse=True)


def test_biotools_high_impact_wins_over_relevance(biotools_registry):
    tools = [
        _biotools_tool("High Impact Low Relevance", 1000, topic="Genomics"),
        _biotools_tool("Low Impact High Relevance", 10, topic="RNA-Seq"),
    ]
    with patch.object(biotools_registry, "_fetch_tools", return_value=tools):
        results = biotools_registry.search("rna-seq", limit=10)
    assert results[0]["name"] == "High Impact Low Relevance"


def test_biotools_quality_breaks_citation_ties(biotools_registry):
    tools = [
        _biotools_tool("Low Quality", 100),
        _biotools_tool(
            "High Quality",
            100,
            validated=1,
            homepage_status=1,
            elixir_badge=1,
        ),
    ]
    with patch.object(biotools_registry, "_fetch_tools", return_value=tools):
        results = biotools_registry.search("rna-seq", limit=10)
    assert results[0]["name"] == "High Quality"


def test_biocontext_mcp_sorted_by_stars(biocontext_registry):
    servers = [
        {"name": "Low", "identifier": "low", "description": "x", "keywords": ["RNA-Seq"], "stars": 5},
        {"name": "High", "identifier": "high", "description": "x", "keywords": ["RNA-Seq"], "stars": 200},
        {"name": "Medium", "identifier": "med", "description": "x", "keywords": ["RNA-Seq"], "stars": 50},
    ]
    with patch.object(biocontext_registry.registry_manager, "fetch_registry", return_value=servers):
        results = biocontext_registry.search("rna-seq", limit=10)
    stars = [r.get("stars", 0) for r in results]
    assert stars == sorted(stars, reverse=True)
