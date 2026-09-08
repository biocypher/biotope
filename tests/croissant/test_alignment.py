"""Tests for the alignment over the semantic IR (entity-keyed references)."""

from __future__ import annotations

from pathlib import Path

from biotope.croissant.alignment.model import (
    EquivalenceKind,
)
from biotope.croissant.api import propose_alignment
from biotope.croissant.mapping import Mapping, dump_mapping


def test_propose_alignment_finds_shared_property(tmp_path: Path, two_recordsets_croissant: Path) -> None:
    a = tmp_path / "a.mapping.yaml"
    b = tmp_path / "b.mapping.yaml"
    mapping = Mapping.model_validate(
        {
            "croissant": str(two_recordsets_croissant),
            "entities": {
                "gene": {
                    "record_set": "genes",
                    "id": "gene_id",
                    "properties": {"symbol": "symbol"},
                }
            },
        }
    )
    dump_mapping(mapping, a)
    dump_mapping(mapping, b)

    result = propose_alignment([a, b])
    equivalences = result["alignment"]["equivalences"]
    assert len(equivalences) > 0
    assert all(eq["kind"] == EquivalenceKind.SAME_NODE.value for eq in equivalences)
    assert equivalences[0]["a"]["node_type"] == "gene"
    assert equivalences[0]["b"]["node_type"] == "gene"
    assert equivalences[0]["reason"]
    assert equivalences[0]["confidence"] is not None


def test_propose_alignment_single_mapping_returns_reason(tmp_path: Path, two_recordsets_croissant: Path) -> None:
    a = tmp_path / "a.mapping.yaml"
    mapping = Mapping.model_validate(
        {
            "croissant": str(two_recordsets_croissant),
            "entities": {
                "gene": {
                    "record_set": "genes",
                    "id": "gene_id",
                    "properties": {"symbol": "symbol"},
                }
            },
        }
    )
    dump_mapping(mapping, a)

    result = propose_alignment([a])
    assert result["alignment"]["equivalences"] == []
    assert "reason" in result
    assert ">=2 mappings" in result["reason"]


def _typed_mapping(croissant: Path, entity_key: str, schema_term: str, properties: dict[str, str]) -> Mapping:
    return Mapping.model_validate(
        {
            "croissant": str(croissant),
            "entities": {
                entity_key: {
                    "record_set": "genes",
                    "schema_term": schema_term,
                    "id": "gene_id",
                    "properties": properties,
                }
            },
        }
    )


def test_propose_alignment_cross_type_guard(tmp_path: Path, two_recordsets_croissant: Path) -> None:
    """Different declared types only get proposed via an id-like shared field
    (e.g. `ensembl_id`) — an incidental shared field (e.g. `species`) alone is
    too weak a signal."""
    a, b = tmp_path / "a.mapping.yaml", tmp_path / "b.mapping.yaml"

    dump_mapping(_typed_mapping(two_recordsets_croissant, "gene", "Gene", {"species": "species"}), a)
    dump_mapping(_typed_mapping(two_recordsets_croissant, "tf", "TranscriptionFactor", {"species": "species"}), b)
    assert propose_alignment([a, b])["alignment"]["equivalences"] == []

    props = {"species": "species", "ensembl_id": "ensembl_id"}
    dump_mapping(_typed_mapping(two_recordsets_croissant, "gene", "Gene", props), a)
    dump_mapping(_typed_mapping(two_recordsets_croissant, "tf", "TranscriptionFactor", props), b)
    equivalences = propose_alignment([a, b])["alignment"]["equivalences"]
    assert len(equivalences) == 1
    assert equivalences[0]["join_on"]["a"] == "ensembl_id"
    assert "id-like" in equivalences[0]["reason"]
