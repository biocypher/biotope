"""Tests for the alignment over the semantic IR (entity-keyed references)."""

from __future__ import annotations

from pathlib import Path

from biotope.croissant.alignment.model import (
    Alignment,
    Equivalence,
    EquivalenceKind,
    JoinKeys,
    Reference,
)
from biotope.croissant.api import propose_alignment
from biotope.croissant.mapping import Mapping, dump_mapping


def test_alignment_model_validates() -> None:
    alignment = Alignment(
        mappings=["a.mapping.yaml", "b.mapping.yaml"],
        equivalences=[
            Equivalence(
                a=Reference(mapping="a", node_type="gene"),
                b=Reference(mapping="b", node_type="tf"),
                kind=EquivalenceKind.SAME_NODE,
                join_on=JoinKeys(a="ensembl_id", b="ensembl_id"),
            ),
        ],
    )
    assert alignment.equivalences[0].kind == EquivalenceKind.SAME_NODE


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


def test_merge_rewrites_edge_endpoints_to_aligned_node_ids() -> None:
    """Edges from adapter B must use rewritten node ids after SAME_NODE alignment."""
    from dataclasses import dataclass

    from biotope.croissant.alignment.merge import MergedAdapter
    from biotope.croissant.mapping.model import Mapping

    @dataclass
    class _FakeAdapter:
        mapping: Mapping
        nodes: list[tuple[str, str, dict]]
        edges: list[tuple]

        def get_nodes(self):
            return iter(self.nodes)

        def get_edges(self):
            return iter(self.edges)

    gene_mapping = Mapping.model_validate(
        {
            "croissant": "a.json",
            "entities": {
                "gene": {
                    "record_set": "genes",
                    "id": {
                        "field": "ensembl_id",
                        "transform": "as_curie",
                        "args": {"prefix": "ensembl"},
                    },
                }
            },
        }
    )
    tf_mapping = Mapping.model_validate(
        {
            "croissant": "b.json",
            "entities": {
                "tf": {
                    "record_set": "tfs",
                    "id": {"field": "id"},
                }
            },
        }
    )
    alignment = Alignment(
        mappings=["a", "b"],
        equivalences=[
            Equivalence(
                a=Reference(mapping="a", node_type="gene"),
                b=Reference(mapping="b", node_type="tf"),
                kind=EquivalenceKind.SAME_NODE,
                join_on=JoinKeys(a="ensembl_id", b="ensembl_id"),
            ),
        ],
    )
    adapters = {
        "a": _FakeAdapter(
            gene_mapping,
            [("ensembl:1", "gene", {"ensembl_id": "1"})],
            [],
        ),
        "b": _FakeAdapter(
            tf_mapping,
            [("raw:1", "tf", {"ensembl_id": "1"})],
            [(None, "raw:1", "ext:2", "targets", {})],
        ),
    }
    merged = MergedAdapter(adapters_by_stem=adapters, alignment=alignment)  # type: ignore[arg-type]

    nodes = list(merged.get_nodes())
    edges = list(merged.get_edges())

    assert ("ensembl:1", "tf", {"ensembl_id": "1"}) in nodes
    assert edges == [(None, "ensembl:1", "ext:2", "targets", {})]
