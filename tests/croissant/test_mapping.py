"""Tests for the semantic mapping IR (entities/relations)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from biotope.croissant.acquisition import AcquisitionContext
from biotope.croissant.api import scaffold_mapping
from biotope.croissant.mapping import (
    EntityMapping,
    ExplodeScan,
    Mapping,
    RowScan,
    Selector,
    compile_mapping,
    dump_mapping,
    load_mapping,
    unresolved_scaffold,
)
from biotope.croissant.mapping.model import to_snake_case
from biotope.croissant.spec import load_from_path


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def test_string_shorthand_normalises_to_field_selector() -> None:
    entity = EntityMapping.model_validate(
        {"record_set": "rs", "id": "ensembl_id", "properties": {"symbol": "symbol"}}
    )
    assert entity.id == Selector(field="ensembl_id")
    assert entity.properties["symbol"] == Selector(field="symbol")


def test_selector_rejects_both_field_and_use() -> None:
    with pytest.raises(ValidationError):
        Selector.model_validate({"field": "x", "use": "y"})


def test_scan_coercion_accepts_row_and_explode() -> None:
    e = EntityMapping.model_validate({"scan": "row"})
    assert isinstance(e.scan, RowScan)
    e2 = EntityMapping.model_validate({"scan": {"explode": "diseases"}})
    assert isinstance(e2.scan, ExplodeScan)
    assert e2.scan.axes == {"item": "diseases"}
    assert e2.scan.explode == "diseases"  # single-axis projects as string

    e3 = EntityMapping.model_validate(
        {"scan": {"explode": {"drug": "chemblIds", "target": "targets"}}}
    )
    assert isinstance(e3.scan, ExplodeScan)
    assert e3.scan.axes == {"drug": "chemblIds", "target": "targets"}
    assert e3.scan.explode == {"drug": "chemblIds", "target": "targets"}


def test_legacy_nodes_edges_are_rejected() -> None:
    legacy = {
        "croissant": "x.json",
        "nodes": [{"record_set": "rs", "type": "n", "id": {"from": "id"}}],
    }
    with pytest.raises(ValueError, match="Legacy"):
        Mapping.model_validate(legacy)


def test_snake_case_enforced_on_keys() -> None:
    with pytest.raises(ValidationError):
        Mapping.model_validate(
            {
                "croissant": "x.json",
                "entities": {"BadName": {"record_set": "rs", "id": "id"}},
            }
        )


def test_relation_endpoint_must_reference_known_entity() -> None:
    payload = {
        "croissant": "x.json",
        "entities": {"target": {"record_set": "rs", "id": "id"}},
        "relations": {
            "rel": {
                "record_set": "rs",
                "source": {"entity": "target", "field": "src"},
                "target": {"entity": "missing", "field": "tgt"},
            }
        },
    }
    with pytest.raises(ValidationError, match="unknown entity 'missing'"):
        Mapping.model_validate(payload)


def test_use_in_selector_must_reference_known_id() -> None:
    payload = {
        "croissant": "x.json",
        "entities": {"target": {"record_set": "rs", "id": {"use": "missing"}}},
    }
    with pytest.raises(ValidationError, match="unknown id"):
        Mapping.model_validate(payload)


def test_item_rejected_in_where() -> None:
    payload = {
        "croissant": "x.json",
        "entities": {
            "e": {
                "record_set": "rs",
                "id": "id",
                "where": "score > 0 AND $item.foo > 0",
            }
        },
    }
    with pytest.raises(ValidationError, match=r"\$item.*where"):
        Mapping.model_validate(payload)


def test_item_rejected_when_scan_is_row() -> None:
    payload = {
        "croissant": "x.json",
        "entities": {
            "e": {
                "record_set": "rs",
                "scan": "row",
                "id": {"field": "$item.foo"},
            }
        },
    }
    with pytest.raises(ValidationError, match=r"\$item"):
        Mapping.model_validate(payload)


def test_unresolved_slots_reported() -> None:
    mapping = Mapping.model_validate(
        {
            "croissant": "x.json",
            "entities": {"target": {}, "ready": {"record_set": "rs", "id": "id"}},
            "relations": {"r": {}},
        }
    )
    assert sorted(mapping.unresolved_slots()) == ["entities.target", "relations.r"]
    assert not mapping.is_resolved()
    mapping.entities  # ensure model accessible
    with pytest.raises(ValueError, match="unresolved"):
        mapping.assert_resolved()


def test_to_snake_case_normalises_phrasing() -> None:
    assert to_snake_case("Drug Targets Gene") == "drug_targets_gene"
    assert to_snake_case("which drugs target which proteins") == "which_drugs_target_which_proteins"
    assert to_snake_case("123 leading digit") == "_123_leading_digit"


# ---------------------------------------------------------------------------
# Compile / runtime
# ---------------------------------------------------------------------------


def test_compile_emits_node_tuples(minimal_croissant: Path, gene_csv: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    mapping = Mapping.model_validate(
        {
            "croissant": str(minimal_croissant),
            "entities": {
                "gene": {
                    "record_set": "genes",
                    "id": "ensembl_id",
                    "properties": {"symbol": "symbol", "biotype": "biotype"},
                }
            },
        }
    )
    with AcquisitionContext(dataset, datasets_location=gene_csv.parent) as ctx:
        adapter = compile_mapping(mapping, ctx)
        nodes = list(adapter.get_nodes())
    assert len(nodes) == 2
    node_ids = {n[0] for n in nodes}
    assert "ENSG00000139618" in node_ids
    # input_label is the mapping key
    assert all(n[1] == "gene" for n in nodes)
    assert all(n[2]["symbol"] for n in nodes)


def test_compile_emits_edge_tuples(two_recordsets_croissant: Path, two_recordsets_dir: Path) -> None:
    dataset = load_from_path(two_recordsets_croissant)
    mapping = Mapping.model_validate(
        {
            "croissant": str(two_recordsets_croissant),
            "entities": {
                "gene": {"record_set": "genes", "id": "gene_id"},
                "disease": {"record_set": "gene_disease", "id": "disease_id"},
            },
            "relations": {
                "gene_in_disease": {
                    "record_set": "gene_disease",
                    "source": {"entity": "gene", "field": "gene_id"},
                    "target": {"entity": "disease", "field": "disease_id"},
                    "properties": {"score": "score"},
                }
            },
        }
    )
    with AcquisitionContext(dataset, datasets_location=two_recordsets_dir) as ctx:
        adapter = compile_mapping(mapping, ctx)
        edges = list(adapter.get_edges())
    # BioCypher edge tuple: (rel_id, source_id, target_id, label, properties).
    assert all(e[0] is None for e in edges)
    assert {e[1] for e in edges} == {"G1", "G2"}
    assert all(e[3] == "gene_in_disease" for e in edges)
    assert all("score" in e[4] for e in edges)


def test_edge_tuple_uses_biocypher_5_tuple_shape(
    two_recordsets_croissant: Path, two_recordsets_dir: Path
) -> None:
    """Regression: edges must be (rel_id, src, tgt, label, props), not (src, tgt, label, label, props)."""
    dataset = load_from_path(two_recordsets_croissant)
    mapping = Mapping.model_validate(
        {
            "croissant": str(two_recordsets_croissant),
            "entities": {
                "gene": {"record_set": "genes", "id": "gene_id"},
                "disease": {"record_set": "gene_disease", "id": "disease_id"},
            },
            "relations": {
                "gene_in_disease": {
                    "record_set": "gene_disease",
                    "source": {"entity": "gene", "field": "gene_id"},
                    "target": {"entity": "disease", "field": "disease_id"},
                }
            },
        }
    )
    with AcquisitionContext(dataset, datasets_location=two_recordsets_dir) as ctx:
        adapter = compile_mapping(mapping, ctx)
        edges = list(adapter.get_edges())
    assert edges, "expected at least one edge"
    for tup in edges:
        assert len(tup) == 5, tup
        rel_id, src, tgt, label, props = tup
        assert rel_id is None, "relationship_id should be None in v1"
        assert src in {"G1", "G2"}
        assert tgt in {"D1", "D2"}
        assert label == "gene_in_disease", f"label position is wrong: {tup}"
        assert isinstance(props, dict)


def test_explode_with_item_id_emits_one_node_per_array_element(tmp_path: Path) -> None:
    """Regression: drug entity with `scan: {explode: chemblIds}` + `id: $item` works."""
    croissant_path = tmp_path / "ot.jsonld"
    croissant_path.write_text(
        """
        {"@type":"sc:Dataset","name":"ot",
         "distribution":[{"@id":"moa-fileset","@type":"cr:FileSet",
                          "includes":"moa.csv","encodingFormat":"text/csv"}],
         "recordSet":[{"@id":"moa","name":"moa",
           "field":[
             {"name":"actionType","dataType":"sc:Text"},
             {"name":"chemblIds","dataType":"sc:Text","repeated":true,
              "source":{"fileSet":{"@id":"moa-fileset"}}}
           ]}]}
        """
    )
    # NOTE: CSV doesn't natively store array columns; we use the runtime path that
    # iterates a Python list directly.
    from biotope.croissant.acquisition.context import RecordRow
    from biotope.croissant.mapping.compile import iter_entity_tuples
    from biotope.croissant.spec import load_from_path

    dataset = load_from_path(croissant_path)
    mapping = Mapping.model_validate(
        {
            "croissant": str(croissant_path),
            "entities": {
                "drug": {
                    "record_set": "moa",
                    "scan": {"explode": "chemblIds"},
                    "id": {
                        "field": "$item",
                        "transform": "as_curie",
                        "args": {"prefix": "chembl"},
                    },
                }
            },
        }
    )

    # Build a synthetic context that yields one row with two array elements
    # without needing actual data files.
    class _StubCtx:
        def stream(self, record_set, fields=None, where=None):
            yield RecordRow(
                record_set="moa",
                values={"chemblIds": ["CHEMBL748", "CHEMBL1420"], "actionType": "ACTIVATOR"},
            )

    nodes = list(iter_entity_tuples(mapping, _StubCtx()))
    assert {n[0] for n in nodes} == {"chembl:CHEMBL748", "chembl:CHEMBL1420"}
    assert all(n[1] == "drug" for n in nodes)


def test_multi_axis_explode_cartesian_product(tmp_path: Path) -> None:
    """Two explode axes produce one edge per (axis1, axis2) combination per row."""
    from biotope.croissant.acquisition.context import RecordRow
    from biotope.croissant.mapping.compile import iter_relation_tuples
    from biotope.croissant.spec import load_from_path

    croissant_path = tmp_path / "ot.jsonld"
    croissant_path.write_text(
        """
        {"@type":"sc:Dataset","name":"ot",
         "recordSet":[
           {"@id":"drug","name":"drug","field":[{"name":"chembl","dataType":"sc:Text"}]},
           {"@id":"gene","name":"gene","field":[{"name":"ens","dataType":"sc:Text"}]},
           {"@id":"moa","name":"moa","field":[
              {"name":"chemblIds","dataType":"sc:Text","repeated":true},
              {"name":"targets","dataType":"sc:Text","repeated":true}
           ]}
         ]}
        """
    )
    load_from_path(croissant_path)
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
                    "scan": {"explode": {"drug": "chemblIds", "target": "targets"}},
                    "source": {
                        "entity": "drug",
                        "field": "$drug",
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

    class _StubCtx:
        def stream(self, record_set, fields=None, where=None):
            yield RecordRow(
                record_set="moa",
                values={
                    "chemblIds": ["CHEMBL1", "CHEMBL2"],
                    "targets": ["ENSG1", "ENSG2", "ENSG3"],
                },
            )

    edges = list(iter_relation_tuples(mapping, _StubCtx()))
    # 2 drugs × 3 targets = 6 edges
    assert len(edges) == 6
    pairs = {(e[1], e[2]) for e in edges}
    assert pairs == {
        ("chembl:CHEMBL1", "ensembl:ENSG1"),
        ("chembl:CHEMBL1", "ensembl:ENSG2"),
        ("chembl:CHEMBL1", "ensembl:ENSG3"),
        ("chembl:CHEMBL2", "ensembl:ENSG1"),
        ("chembl:CHEMBL2", "ensembl:ENSG2"),
        ("chembl:CHEMBL2", "ensembl:ENSG3"),
    }
    # Label slot is still at index 3, rel_id is None.
    assert all(e[3] == "drug_has_target" and e[0] is None for e in edges)


def test_multi_axis_explode_excludes_axis_refs_from_projection(tmp_path: Path) -> None:
    """`$<axis>` selectors must NOT end up in the DuckDB column projection.

    Regression for the `Binder Error: Referenced column "$chembl" not found` bug.
    """
    from biotope.croissant.mapping.compile import _relation_fields

    mapping = Mapping.model_validate(
        {
            "croissant": "x.json",
            "entities": {"e": {"record_set": "rs", "id": "id"}},
            "relations": {
                "r": {
                    "record_set": "rs",
                    "scan": {"explode": {"chembl": "chemblIds", "target": "targets"}},
                    "source": {
                        "entity": "e",
                        "field": "$chembl",
                        "transform": "as_curie",
                        "args": {"prefix": "chembl"},
                    },
                    "target": {
                        "entity": "e",
                        "field": "$target",
                        "transform": "as_curie",
                        "args": {"prefix": "ensembl"},
                    },
                }
            },
        }
    )
    projected = _relation_fields(mapping.relations["r"]) or []
    # Must include the array fields themselves (we need to read them) but never
    # the `$<axis>` placeholders.
    assert "chemblIds" in projected and "targets" in projected
    assert not any(p.startswith("$") for p in projected), projected


def test_multi_axis_explode_rejects_unknown_axis_in_selector(tmp_path: Path) -> None:
    """Selectors that reference a `$<axis>` not declared in the scan must fail validation."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="is not an axis"):
        Mapping.model_validate(
            {
                "croissant": "x.json",
                "entities": {"e": {"record_set": "rs", "id": "id"}},
                "relations": {
                    "r": {
                        "record_set": "rs",
                        "scan": {"explode": {"drug": "chemblIds"}},
                        "source": {"entity": "e", "field": "$drug"},
                        "target": {"entity": "e", "field": "$mystery"},
                    }
                },
            }
        )


def test_multi_axis_explode_round_trip_yaml(tmp_path: Path) -> None:
    """Multi-axis YAML must serialise back to a dict form (not a bare string)."""
    mapping = Mapping.model_validate(
        {
            "croissant": "x.json",
            "entities": {"e": {"record_set": "rs", "id": "id"}},
            "relations": {
                "r": {
                    "record_set": "rs",
                    "scan": {"explode": {"drug": "chemblIds", "tgt": "targets"}},
                    "source": {"entity": "e", "field": "$drug"},
                    "target": {"entity": "e", "field": "$tgt"},
                }
            },
        }
    )
    yaml_path = tmp_path / "m.mapping.yaml"
    dump_mapping(mapping, yaml_path)
    reloaded = load_mapping(yaml_path)
    rel_scan = reloaded.relations["r"].scan
    assert isinstance(rel_scan, ExplodeScan)
    assert rel_scan.axes == {"drug": "chemblIds", "tgt": "targets"}


def test_explode_with_raw_field_id_drops_rows_under_scalar_guard(tmp_path: Path) -> None:
    """The OP's bug: explode scan + `id: chemblIds` (raw field) yields lists → all dropped."""
    croissant_path = tmp_path / "ot.jsonld"
    croissant_path.write_text(
        """
        {"@type":"sc:Dataset","name":"ot",
         "recordSet":[{"@id":"moa","name":"moa",
           "field":[
             {"name":"chemblIds","dataType":"sc:Text","repeated":true}
           ]}]}
        """
    )
    from biotope.croissant.acquisition.context import RecordRow
    from biotope.croissant.mapping.compile import iter_entity_tuples
    from biotope.croissant.spec import load_from_path

    load_from_path(croissant_path)
    mapping = Mapping.model_validate(
        {
            "croissant": str(croissant_path),
            "entities": {
                "drug": {
                    "record_set": "moa",
                    "scan": {"explode": "chemblIds"},
                    "id": "chemblIds",  # wrong: reads the whole array from the base row
                }
            },
        }
    )

    class _StubCtx:
        def stream(self, record_set, fields=None, where=None):
            yield RecordRow(record_set="moa", values={"chemblIds": ["A", "B"]})

    nodes = list(iter_entity_tuples(mapping, _StubCtx()))
    assert nodes == [], "non-scalar ids must be dropped, not emitted as 'list literals'"


def test_named_id_via_use(minimal_croissant: Path, gene_csv: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    mapping = Mapping.model_validate(
        {
            "croissant": str(minimal_croissant),
            "ids": {
                "gene_curie": {
                    "field": "ensembl_id",
                    "transform": "as_curie",
                    "args": {"prefix": "ensembl"},
                }
            },
            "entities": {
                "gene": {
                    "record_set": "genes",
                    "id": {"use": "gene_curie"},
                }
            },
        }
    )
    with AcquisitionContext(dataset, datasets_location=gene_csv.parent) as ctx:
        nodes = list(compile_mapping(mapping, ctx).get_nodes())
    assert all(n[0].startswith("ensembl:ENSG") for n in nodes)


def test_hash_id_skips_when_field_missing(minimal_croissant: Path, gene_csv: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    mapping = Mapping.model_validate(
        {
            "croissant": str(minimal_croissant),
            "entities": {
                "gene": {
                    "record_set": "genes",
                    "id": {
                        "transform": "hash_id",
                        "args": {"fields": ["ensembl_id", "symbol"], "prefix": "g"},
                    },
                }
            },
        }
    )
    with AcquisitionContext(dataset, datasets_location=gene_csv.parent) as ctx:
        nodes = list(compile_mapping(mapping, ctx).get_nodes())
    assert all(n[0].startswith("g:") for n in nodes)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_round_trip_yaml(minimal_croissant: Path, tmp_path: Path) -> None:
    mapping = Mapping.model_validate(
        {
            "croissant": str(minimal_croissant),
            "entities": {"gene": {"record_set": "genes", "id": "ensembl_id"}},
        }
    )
    yaml_path = tmp_path / "minimal.mapping.yaml"
    dump_mapping(mapping, yaml_path)
    reloaded = load_mapping(yaml_path)
    assert reloaded.entities["gene"].record_set == "genes"
    assert reloaded.entities["gene"].id == Selector(field="ensembl_id")


def test_legacy_loader_message(tmp_path: Path) -> None:
    legacy_path = tmp_path / "legacy.mapping.yaml"
    legacy_path.write_text(
        yaml.safe_dump(
            {
                "croissant": "x.json",
                "nodes": [{"record_set": "rs", "type": "n", "id": {"from": "id"}}],
            }
        )
    )
    with pytest.raises(ValueError, match="biotope map scaffold"):
        load_mapping(legacy_path)


# ---------------------------------------------------------------------------
# Scaffold (heuristic-free)
# ---------------------------------------------------------------------------


def test_unresolved_scaffold_keys_from_intent() -> None:
    mapping = unresolved_scaffold(
        "x.json",
        required_entities=["Gene", "Disease"],
        required_relations=["which genes are in which diseases"],
    )
    assert set(mapping.entities) == {"gene", "disease"}
    assert "which_genes_are_in_which_diseases" in mapping.relations
    # All slots unresolved
    assert not mapping.is_resolved()


def test_scaffold_mapping_writes_appendix(minimal_croissant: Path, gene_csv: Path, tmp_path: Path) -> None:
    croissant_path = tmp_path / "minimal.croissant.json"
    croissant_path.write_text(minimal_croissant.read_text())
    (tmp_path / "genes.csv").write_text(gene_csv.read_text())

    out = tmp_path / "minimal.mapping.yaml"
    result = scaffold_mapping(
        croissant_path,
        required_entities=["gene"],
        required_relations=[],
        write_to=out,
    )
    text = out.read_text()
    assert "# Croissant inspection appendix" in text
    assert "Record set: genes" in text
    assert "Intent captured from project.yaml:" in text
    assert "entities.gene" in result["unresolved"]
