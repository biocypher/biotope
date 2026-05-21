"""Tests for the preview engine."""
from __future__ import annotations

from pathlib import Path

from biotope.croissant.mapping import Mapping, preview_mapping
from biotope.croissant.spec import load_from_path


def _load_dataset(croissant: Path) -> object:
    return load_from_path(croissant)


def test_partial_mapping_reports_unresolved_slots(minimal_croissant: Path) -> None:
    mapping = Mapping.model_validate(
        {
            "croissant": str(minimal_croissant),
            "entities": {"gene": {}},
            "relations": {"gene_in_disease": {}},
        }
    )
    result = preview_mapping(mapping, _load_dataset(minimal_croissant))
    assert "entities.gene" in result.unresolved_slots
    assert "relations.gene_in_disease" in result.unresolved_slots
    assert result.entities == []
    assert result.relations == []


def test_validation_flags_missing_record_set(minimal_croissant: Path) -> None:
    mapping = Mapping.model_validate(
        {
            "croissant": str(minimal_croissant),
            "entities": {"gene": {"record_set": "nope", "id": "x"}},
        }
    )
    result = preview_mapping(mapping, _load_dataset(minimal_croissant))
    assert any(
        f.severity == "error" and "unknown record_set" in f.message for f in result.findings
    )


def test_validation_flags_unknown_field(minimal_croissant: Path) -> None:
    mapping = Mapping.model_validate(
        {
            "croissant": str(minimal_croissant),
            "entities": {"gene": {"record_set": "genes", "id": "ghost_field"}},
        }
    )
    result = preview_mapping(mapping, _load_dataset(minimal_croissant))
    assert any("ghost_field" in f.message for f in result.findings)


def test_resolved_entity_projected_with_namespace(minimal_croissant: Path) -> None:
    mapping = Mapping.model_validate(
        {
            "croissant": str(minimal_croissant),
            "entities": {
                "gene": {
                    "record_set": "genes",
                    "id": {
                        "field": "ensembl_id",
                        "transform": "as_curie",
                        "args": {"prefix": "ensembl"},
                    },
                    "properties": {"symbol": "symbol"},
                }
            },
        }
    )
    result = preview_mapping(mapping, _load_dataset(minimal_croissant))
    assert len(result.entities) == 1
    ent = result.entities[0]
    assert ent.namespace == "ensembl"
    assert ent.input_label == "gene"
    assert ent.schema_term == "gene"
    assert "symbol" in ent.properties


def test_preview_rejects_array_field_as_id_under_row_scan(tmp_path) -> None:
    """An array-typed field used as `id` with `scan: row` should produce an error finding."""
    croissant_path = tmp_path / "ot.jsonld"
    croissant_path.write_text(
        """
        {
          "@type": "sc:Dataset",
          "name": "ot",
          "recordSet": [{
            "@id": "drug", "name": "drug",
            "field": [
              {"name": "chemblIds", "dataType": "sc:Text", "repeated": true},
              {"name": "name", "dataType": "sc:Text"}
            ]
          }]
        }
        """
    )
    from biotope.croissant.spec import load_from_path

    mapping = Mapping.model_validate(
        {
            "croissant": str(croissant_path),
            "entities": {
                "drug": {"record_set": "drug", "id": "chemblIds", "properties": {"name": "name"}}
            },
        }
    )
    result = preview_mapping(mapping, load_from_path(croissant_path))
    errors = [f for f in result.findings if f.severity == "error"]
    assert any("array-typed" in f.message for f in errors), [
        (f.severity, f.path, f.message) for f in result.findings
    ]


def test_preview_warns_when_source_equals_target_field(tmp_path) -> None:
    """A relation whose source and target read the same field should warn (self-loops)."""
    croissant_path = tmp_path / "ot.jsonld"
    croissant_path.write_text(
        """
        {
          "@type": "sc:Dataset",
          "name": "ot",
          "recordSet": [{
            "@id": "rs", "name": "rs",
            "field": [{"name": "id", "dataType": "sc:Text"}]
          }]
        }
        """
    )
    from biotope.croissant.spec import load_from_path

    mapping = Mapping.model_validate(
        {
            "croissant": str(croissant_path),
            "entities": {"e": {"record_set": "rs", "id": "id"}},
            "relations": {
                "self_loop": {
                    "record_set": "rs",
                    "source": {"entity": "e", "field": "id"},
                    "target": {"entity": "e", "field": "id"},
                }
            },
        }
    )
    result = preview_mapping(mapping, load_from_path(croissant_path))
    warnings = [f for f in result.findings if f.severity == "warning"]
    assert any("self-loops" in f.message for f in warnings)


def test_preview_emits_sample_tuples_when_data_available(
    minimal_croissant: Path,
    gene_csv: Path,
    tmp_path: Path,
) -> None:
    croissant_path = tmp_path / "minimal.croissant.json"
    croissant_path.write_text(minimal_croissant.read_text())
    (tmp_path / "genes.csv").write_text(gene_csv.read_text())

    mapping = Mapping.model_validate(
        {
            "croissant": str(croissant_path),
            "entities": {
                "gene": {
                    "record_set": "genes",
                    "id": "ensembl_id",
                    "properties": {"symbol": "symbol"},
                }
            },
        }
    )
    result = preview_mapping(
        mapping, load_from_path(croissant_path), datasets_location=tmp_path, sample_rows=2
    )
    assert len(result.sample_node_tuples) >= 1
    node = result.sample_node_tuples[0]
    assert node[1] == "gene"
