"""Tests for the preview engine."""

from __future__ import annotations

from pathlib import Path

from biotope.croissant.mapping import Mapping, aggregate_previews, preview_mapping
from biotope.croissant.spec import load_from_path


def _load_dataset(croissant: Path) -> object:
    return load_from_path(croissant)


def test_partial_mapping_reports_unresolved_slots(minimal_croissant: Path) -> None:
    """Partial slots (record_set set but binding incomplete) are reported.

    Truly empty stubs (no fields touched) are scaffolded TODOs, not authoring
    errors, and don't show up in the preview's unresolved list.
    """
    mapping = Mapping.model_validate(
        {
            "croissant": str(minimal_croissant),
            "entities": {"gene": {"record_set": "genes"}},
            "relations": {"gene_in_disease": {"record_set": "genes"}},
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
    assert any(f.severity == "error" and "unknown record_set" in f.message for f in result.findings)


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
            "entities": {"drug": {"record_set": "drug", "id": "chemblIds", "properties": {"name": "name"}}},
        }
    )
    result = preview_mapping(mapping, load_from_path(croissant_path))
    errors = [f for f in result.findings if f.severity == "error"]
    assert any("array-typed" in f.message for f in errors), [(f.severity, f.path, f.message) for f in result.findings]


def test_preview_does_not_warn_on_axis_selectors(tmp_path) -> None:
    """`$<axis>` references must not be flagged as 'field not declared on record set'."""
    croissant_path = tmp_path / "ot.jsonld"
    croissant_path.write_text(
        """
        {
          "@type":"sc:Dataset","name":"ot",
          "recordSet":[
            {"@id":"drug","name":"drug","field":[{"name":"chembl","dataType":"sc:Text"}]},
            {"@id":"gene","name":"gene","field":[{"name":"ens","dataType":"sc:Text"}]},
            {"@id":"moa","name":"moa","field":[
              {"name":"chemblIds","dataType":"sc:Text","repeated":true},
              {"name":"targets","dataType":"sc:Text","repeated":true}
            ]}
          ]
        }
        """
    )
    from biotope.croissant.spec import load_from_path

    mapping = Mapping.model_validate(
        {
            "croissant": str(croissant_path),
            "entities": {
                "drug": {"record_set": "drug", "id": "chembl"},
                "gene": {"record_set": "gene", "id": "ens"},
            },
            "relations": {
                "drug_has_target": {
                    "record_set": "moa",
                    "scan": {"explode": {"chembl": "chemblIds", "target": "targets"}},
                    "source": {
                        "entity": "drug",
                        "field": "$chembl",
                        "transform": "as_curie",
                        "args": {"prefix": "chembl"},
                    },
                    "target": {
                        "entity": "gene",
                        "field": "$target",
                        "transform": "as_curie",
                        "args": {"prefix": "ensembl"},
                    },
                }
            },
        }
    )
    result = preview_mapping(mapping, load_from_path(croissant_path))
    bad = [f for f in result.findings if "$" in f.message and "not declared on the chosen record set" in f.message]
    assert bad == [], f"axis selectors falsely flagged: {bad}"


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
    result = preview_mapping(mapping, load_from_path(croissant_path), datasets_location=tmp_path, sample_rows=2)
    assert len(result.sample_node_tuples) >= 1
    node = result.sample_node_tuples[0]
    assert node[1] == "gene"


# ---------------------------------------------------------------------------
# Multi-mapping aggregation
# ---------------------------------------------------------------------------


def _two_file_setup(tmp_path: Path) -> tuple[object, object]:
    """Build two Croissant files + two mapping previews matching the airports tutorial:
    file A defines entity `airport` (with properties) and relation `number_of_flights`;
    file B defines entity `airline` and relation `is_hub_for` (airport->airline).
    """
    a_path = tmp_path / "a.jsonld"
    a_path.write_text(
        """
        {"@type":"sc:Dataset","name":"a","recordSet":[
          {"@id":"airports","name":"airports","field":[
            {"name":"iata","dataType":"sc:Text"},
            {"name":"name","dataType":"sc:Text"},
            {"name":"city","dataType":"sc:Text"}]},
          {"@id":"flights","name":"flights","field":[
            {"name":"origin","dataType":"sc:Text"},
            {"name":"destination","dataType":"sc:Text"},
            {"name":"count","dataType":"sc:Integer"}]}
        ]}
        """
    )
    b_path = tmp_path / "b.jsonld"
    b_path.write_text(
        """
        {"@type":"sc:Dataset","name":"b","recordSet":[
          {"@id":"hubs","name":"hubs","field":[
            {"name":"airport_iata","dataType":"sc:Text"},
            {"name":"airline_code","dataType":"sc:Text"},
            {"name":"airline_name","dataType":"sc:Text"}]}
        ]}
        """
    )

    mapping_a = Mapping.model_validate(
        {
            "croissant": str(a_path),
            "entities": {
                "airport": {
                    "record_set": "airports",
                    "id": "iata",
                    "properties": {"name": "name", "city": "city"},
                },
                "airline": {},
            },
            "relations": {
                "number_of_flights": {
                    "record_set": "flights",
                    "source": {"entity": "airport", "field": "origin"},
                    "target": {"entity": "airport", "field": "destination"},
                    "properties": {"count": "count"},
                },
                "is_hub_for": {},
            },
        }
    )
    mapping_b = Mapping.model_validate(
        {
            "croissant": str(b_path),
            "entities": {
                "airport": {},
                "airline": {
                    "record_set": "hubs",
                    "id": "airline_code",
                    "properties": {"airline_name": "airline_name"},
                },
            },
            "relations": {
                "is_hub_for": {
                    "record_set": "hubs",
                    "source": {"entity": "airport", "field": "airport_iata"},
                    "target": {"entity": "airline", "field": "airline_code"},
                },
                "number_of_flights": {},
            },
        }
    )
    pa = preview_mapping(mapping_a, load_from_path(a_path))
    pb = preview_mapping(mapping_b, load_from_path(b_path))
    return pa, pb


def test_aggregate_merges_entities_across_files(tmp_path: Path) -> None:
    pa, pb = _two_file_setup(tmp_path)
    agg = aggregate_previews([("a.mapping.yaml", pa), ("b.mapping.yaml", pb)])
    keys = {e.key for e in agg.entities}
    assert keys == {"airport", "airline"}
    airport = next(e for e in agg.entities if e.key == "airport")
    assert airport.sources == ["a.mapping.yaml"]
    airline = next(e for e in agg.entities if e.key == "airline")
    assert airline.sources == ["b.mapping.yaml"]


def test_aggregate_builds_relation_topology(tmp_path: Path) -> None:
    pa, pb = _two_file_setup(tmp_path)
    agg = aggregate_previews([("a.mapping.yaml", pa), ("b.mapping.yaml", pb)])
    rels = {r.key: r for r in agg.relations}
    assert rels["number_of_flights"].source_entity_key == "airport"
    assert rels["number_of_flights"].target_entity_key == "airport"
    assert rels["is_hub_for"].source_entity_key == "airport"
    assert rels["is_hub_for"].target_entity_key == "airline"


def test_aggregate_slot_resolution_index(tmp_path: Path) -> None:
    pa, pb = _two_file_setup(tmp_path)
    agg = aggregate_previews([("a.mapping.yaml", pa), ("b.mapping.yaml", pb)])
    assert agg.slot_resolution["entities.airport"] == ["a.mapping.yaml"]
    assert agg.slot_resolution["entities.airline"] == ["b.mapping.yaml"]
    assert agg.slot_resolution["relations.number_of_flights"] == ["a.mapping.yaml"]
    assert agg.slot_resolution["relations.is_hub_for"] == ["b.mapping.yaml"]


def test_aggregate_flags_double_resolution(tmp_path: Path) -> None:
    """If two files both resolve the same slot, the aggregator warns."""
    croissant_path = tmp_path / "c.jsonld"
    croissant_path.write_text(
        """
        {"@type":"sc:Dataset","name":"c","recordSet":[
          {"@id":"genes","name":"genes","field":[
            {"name":"ensembl_id","dataType":"sc:Text"},
            {"name":"symbol","dataType":"sc:Text"}]}
        ]}
        """
    )
    body = {
        "croissant": str(croissant_path),
        "entities": {"gene": {"record_set": "genes", "id": "ensembl_id"}},
    }
    pa = preview_mapping(Mapping.model_validate(body), load_from_path(croissant_path))
    pb = preview_mapping(Mapping.model_validate(body), load_from_path(croissant_path))
    agg = aggregate_previews([("a.mapping.yaml", pa), ("b.mapping.yaml", pb)])
    assert agg.slot_resolution["entities.gene"] == ["a.mapping.yaml", "b.mapping.yaml"]
    assert any("resolved by multiple" in f.message for f in agg.findings)


def test_aggregate_flags_endpoint_conflict(tmp_path: Path) -> None:
    """Same relation key with different endpoints across files → warning."""
    croissant_path = tmp_path / "d.jsonld"
    croissant_path.write_text(
        """
        {"@type":"sc:Dataset","name":"d","recordSet":[
          {"@id":"rs","name":"rs","field":[
            {"name":"a","dataType":"sc:Text"},
            {"name":"b","dataType":"sc:Text"}]}
        ]}
        """
    )
    base = {
        "croissant": str(croissant_path),
        "entities": {
            "x": {"record_set": "rs", "id": "a"},
            "y": {"record_set": "rs", "id": "b"},
        },
    }
    a_body = {
        **base,
        "relations": {
            "rel": {
                "record_set": "rs",
                "source": {"entity": "x", "field": "a"},
                "target": {"entity": "y", "field": "b"},
            }
        },
    }
    b_body = {
        **base,
        "relations": {
            "rel": {
                "record_set": "rs",
                "source": {"entity": "y", "field": "b"},
                "target": {"entity": "x", "field": "a"},
            }
        },
    }
    pa = preview_mapping(Mapping.model_validate(a_body), load_from_path(croissant_path))
    pb = preview_mapping(Mapping.model_validate(b_body), load_from_path(croissant_path))
    agg = aggregate_previews([("a.mapping.yaml", pa), ("b.mapping.yaml", pb)])
    assert any("endpoints disagree" in f.message for f in agg.findings)
