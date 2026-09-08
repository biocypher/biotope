"""Tests for the semantic mapping IR (entities/relations)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from biotope.croissant.api import scaffold_mapping
from biotope.croissant.mapping import (
    EntityMapping,
    ExplodeScan,
    Mapping,
    RowScan,
    Selector,
    dump_mapping,
    load_mapping,
    unresolved_scaffold,
)
from biotope.croissant.mapping.model import to_snake_case


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def test_string_shorthand_normalises_to_field_selector() -> None:
    entity = EntityMapping.model_validate({"record_set": "rs", "id": "ensembl_id", "properties": {"symbol": "symbol"}})
    assert entity.id == Selector(field="ensembl_id")
    assert entity.properties["symbol"] == Selector(field="symbol")


def test_selector_rejects_both_field_and_use() -> None:
    with pytest.raises(ValidationError):
        Selector.model_validate({"field": "x", "use": "y"})


def test_selector_rejects_field_and_value_together() -> None:
    with pytest.raises(ValidationError):
        Selector.model_validate({"field": "x", "value": "y"})


def test_selector_literal_value_is_resolved() -> None:
    selector = Selector.model_validate({"value": "mondo:0005267"})
    assert selector.is_resolved()
    assert selector.field is None
    assert selector.use is None


def test_scan_coercion_accepts_row_and_explode() -> None:
    e = EntityMapping.model_validate({"scan": "row"})
    assert isinstance(e.scan, RowScan)
    e2 = EntityMapping.model_validate({"scan": {"explode": "diseases"}})
    assert isinstance(e2.scan, ExplodeScan)
    assert e2.scan.axes == {"item": "diseases"}
    assert e2.scan.explode == "diseases"  # single-axis projects as string

    e3 = EntityMapping.model_validate({"scan": {"explode": {"drug": "chemblIds", "target": "targets"}}})
    assert isinstance(e3.scan, ExplodeScan)
    assert e3.scan.axes == {"drug": "chemblIds", "target": "targets"}
    assert e3.scan.explode == {"drug": "chemblIds", "target": "targets"}


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
    """Partial slots (started but not finished) are unresolved; empty stubs are not.

    Intent capture seeds empty stubs into every mapping in the project — they
    mark "declared somewhere, not bound here" and don't block the build.
    Anything past that initial state (e.g. ``record_set`` set but no ``id``)
    is a real authoring gap and gets flagged.
    """
    mapping = Mapping.model_validate(
        {
            "croissant": "x.json",
            "entities": {
                "empty_stub": {},  # untouched; intent-seeded
                "started": {"record_set": "rs"},  # partial — record_set without id
                "ready": {"record_set": "rs", "id": "id"},
            },
            "relations": {
                "empty_rel": {},
                "started_rel": {"record_set": "rs"},
            },
        }
    )
    assert sorted(mapping.unresolved_slots()) == [
        "entities.started",
        "relations.started_rel",
    ]
    assert not mapping.is_resolved()
    with pytest.raises(ValueError, match="unresolved"):
        mapping.assert_resolved()


def test_empty_stubs_pass_resolution() -> None:
    """A mapping containing only empty stubs alongside resolved slots is resolved."""
    mapping = Mapping.model_validate(
        {
            "croissant": "x.json",
            "entities": {
                "stub": {},
                "ready": {"record_set": "rs", "id": "id"},
            },
        }
    )
    assert mapping.is_resolved()
    assert mapping.unresolved_slots() == []


def test_to_snake_case_normalises_phrasing() -> None:
    assert to_snake_case("Drug Targets Gene") == "drug_targets_gene"
    assert to_snake_case("which drugs target which proteins") == "which_drugs_target_which_proteins"
    assert to_snake_case("123 leading digit") == "_123_leading_digit"


# ---------------------------------------------------------------------------
# Compile / runtime
# ---------------------------------------------------------------------------


def test_deferred_relation_definition_state(two_recordsets_croissant: Path) -> None:
    """A deferred relation (data can't support it) is honestly skipped, not an error."""

    mapping = Mapping.model_validate(
        {
            "croissant": str(two_recordsets_croissant),
            "entities": {
                "gene": {"record_set": "genes", "id": "gene_id"},
                "disease": {"record_set": "gene_disease", "id": "disease_id"},
            },
            "relations": {
                "gene_in_disease": {
                    "deferred": True,
                }
            },
        }
    )
    assert mapping.unresolved_slots() == []
    assert mapping.deferred_relations() == ["gene_in_disease"]
    from biotope.croissant.mapping import preview_mapping
    from biotope.croissant.spec import load_from_path

    result = preview_mapping(mapping, load_from_path(two_recordsets_croissant))
    assert result.deferred_slots == ["relations.gene_in_disease"]
    assert result.unresolved_slots == []
    assert result.findings == []
    assert result.relations == []


def test_map_defer_relation_cli_roundtrip(tmp_path: Path, two_recordsets_croissant: Path) -> None:
    from click.testing import CliRunner

    from biotope.commands.map import defer_relation, undefer_relation

    mapping_path = tmp_path / "x.mapping.yaml"
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
    dump_mapping(mapping, mapping_path)

    runner = CliRunner()
    result = runner.invoke(defer_relation, [str(mapping_path), "gene_in_disease"])
    assert result.exit_code == 0, result.output
    reloaded = load_mapping(mapping_path)
    assert reloaded.relations["gene_in_disease"].is_deferred()
    import json

    from biotope.cli import cli

    checked = runner.invoke(cli, ["map", "preview", str(mapping_path), "--json"])
    assert checked.exit_code == 0, checked.output
    payload = json.loads(checked.output)
    local = payload["mappings"][mapping_path.name]
    assert local["deferred_slots"] == ["relations.gene_in_disease"]
    assert "relations.gene_in_disease" not in local["resolved_slots"]
    assert local["schema"]["relations"] == []
    assert payload["global"]["slot_deferred"] == {"relations.gene_in_disease": [mapping_path.name]}
    displayed = runner.invoke(cli, ["map", "preview", str(mapping_path)])
    assert displayed.exit_code == 0, displayed.output
    assert "deferred" in displayed.output.lower()

    result = runner.invoke(undefer_relation, [str(mapping_path), "gene_in_disease"])
    assert result.exit_code == 0, result.output
    reloaded = load_mapping(mapping_path)
    assert not reloaded.relations["gene_in_disease"].is_deferred()
    checked = runner.invoke(cli, ["map", "preview", str(mapping_path), "--json"])
    assert checked.exit_code == 0, checked.output
    local = json.loads(checked.output)["mappings"][mapping_path.name]
    assert local["deferred_slots"] == []
    assert "relations.gene_in_disease" in local["resolved_slots"]
    assert len(local["schema"]["relations"]) == 1


def test_map_defer_relation_unknown_name_errors(tmp_path: Path, two_recordsets_croissant: Path) -> None:
    from click.testing import CliRunner

    from biotope.commands.map import defer_relation

    mapping_path = tmp_path / "x.mapping.yaml"
    mapping = Mapping.model_validate({"croissant": str(two_recordsets_croissant)})
    dump_mapping(mapping, mapping_path)

    runner = CliRunner()
    result = runner.invoke(defer_relation, [str(mapping_path), "nope"])
    assert result.exit_code != 0
    assert "Unknown relation" in result.output


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
    # Scaffolded slots are empty stubs — declared, not yet bound. They don't
    # count as "unresolved" (a state reserved for slots the user started
    # binding without finishing). Slot-first navigation surfaces them as
    # "available to bind" via the project's intent table, not via this method.
    assert mapping.unresolved_slots() == []
    assert mapping.is_resolved()


def test_scaffold_mapping_writes_appendix(minimal_croissant: Path, tmp_path: Path) -> None:
    croissant_path = tmp_path / "minimal.croissant.json"
    croissant_path.write_text(minimal_croissant.read_text())

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
