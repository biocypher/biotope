"""Tests for the wizard's two-way slot sync against project.yaml intent."""

from __future__ import annotations

from biotope.commands.map_wizard import _sync_slots_from_intent
from biotope.project_model import Project


def _project(*, entities: list[str] = None, relations: list[str] = None) -> Project:
    return Project(
        name="t",
        required_entities=entities or [],
        required_relations=relations or [],
    )


def test_sync_adds_new_slots_from_intent() -> None:
    draft = {"croissant": "x.json"}
    project = _project(entities=["drug", "disease"], relations=["drug_in_disease"])

    synced = _sync_slots_from_intent(draft, project)

    assert set(synced["entities"]) == {"drug", "disease"}
    assert set(synced["relations"]) == {"drug_in_disease"}


def test_sync_drops_relation_when_intent_drops_it() -> None:
    """Removing a relation from intent must drop its slot in the draft."""
    draft = {
        "croissant": "x.json",
        "entities": {"drug": {"record_set": "rs", "id": "id"}},
        "relations": {
            "kept": {"record_set": "rs"},
            "dropped": {"record_set": "rs"},  # not in new intent
        },
    }
    project = _project(entities=["drug"], relations=["kept"])

    synced = _sync_slots_from_intent(draft, project)

    assert set(synced["relations"]) == {"kept"}


def test_sync_clears_broken_endpoints_after_entity_removed() -> None:
    """If a relation still in intent points at a removed entity, the endpoint is cleared."""
    draft = {
        "croissant": "x.json",
        "entities": {
            "drug": {"record_set": "rs", "id": "id"},
            "disease": {"record_set": "rs", "id": "id"},
        },
        "relations": {
            "drug_in_disease": {
                "record_set": "rs",
                "source": {"entity": "drug", "field": "x"},
                "target": {"entity": "disease", "field": "y"},
            },
            "disease_in_pathway": {
                "record_set": "rs",
                "source": {"entity": "disease", "field": "x"},
                "target": {"entity": "disease", "field": "y"},
            },
        },
    }
    # `disease` dropped from intent; both relations still in intent.
    project = _project(entities=["drug"], relations=["drug_in_disease", "disease_in_pathway"])

    synced = _sync_slots_from_intent(draft, project)

    assert set(synced["entities"]) == {"drug"}
    # Both relation slots survive (intent still wants them) but their broken
    # endpoints are cleared.
    assert set(synced["relations"]) == {"drug_in_disease", "disease_in_pathway"}
    assert "target" not in synced["relations"]["drug_in_disease"]  # cleared
    assert synced["relations"]["drug_in_disease"]["source"]["entity"] == "drug"  # untouched
    assert "source" not in synced["relations"]["disease_in_pathway"]
    assert "target" not in synced["relations"]["disease_in_pathway"]


def test_sync_keeps_unrelated_endpoints_when_other_entity_removed() -> None:
    """Endpoint clearing only touches sides that actually referenced the removed entity."""
    draft = {
        "entities": {"a": {}, "b": {}, "c": {}},
        "relations": {
            "a_to_b": {"source": {"entity": "a"}, "target": {"entity": "b"}},
            "b_to_c": {"source": {"entity": "b"}, "target": {"entity": "c"}},
        },
    }
    project = _project(entities=["b", "c"], relations=["a_to_b", "b_to_c"])

    synced = _sync_slots_from_intent(draft, project)

    assert "a" not in synced["entities"]
    # a_to_b: source was `a` → cleared; target was `b` → preserved.
    assert "source" not in synced["relations"]["a_to_b"]
    assert synced["relations"]["a_to_b"]["target"]["entity"] == "b"
    # b_to_c: untouched.
    assert synced["relations"]["b_to_c"]["source"]["entity"] == "b"
    assert synced["relations"]["b_to_c"]["target"]["entity"] == "c"


def test_sync_drops_relation_whose_intent_is_gone_regardless_of_entities() -> None:
    """Direct relation removal still works (the OP's case)."""
    draft = {
        "entities": {"drug": {}, "disease": {}},
        "relations": {
            "drug_approved_in_disease": {
                "source": {"entity": "drug"},
                "target": {"entity": "disease"},
            }
        },
    }
    project = _project(entities=["drug", "disease"], relations=[])

    synced = _sync_slots_from_intent(draft, project)

    assert synced["relations"] == {}
