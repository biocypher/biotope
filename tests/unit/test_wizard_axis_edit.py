"""Tests for axis-edit diff and selector rewriting in the wizard."""
from __future__ import annotations

from biotope.commands.map_wizard import (
    _apply_scan_change,
    _diff_axes,
    _rewrite_axis_refs,
    _rewrite_selector,
)


def test_diff_detects_rename_when_field_preserved() -> None:
    old = {"explode": {"drug": "drugIds", "target": "targetIds"}}
    new = {"explode": {"compound": "drugIds", "target": "targetIds"}}

    renames, removed = _diff_axes(old, new)

    assert renames == {"drug": "compound"}
    assert removed == []


def test_diff_detects_removed_when_field_disappears() -> None:
    old = {"explode": {"drug": "drugIds", "target": "targetIds"}}
    new = {"explode": "drugIds"}  # collapses to single axis "item"

    renames, removed = _diff_axes(old, new)

    # "drug" field survives but is now under axis "item" → rename drug→item.
    # "target" field is gone → removed.
    assert renames == {"drug": "item"}
    assert removed == ["target"]


def test_diff_handles_paired_rename() -> None:
    """When two names disappear and reappear, pair by field to recover both renames."""
    old = {"explode": {"drug": "fieldA", "target": "fieldB"}}
    new = {"explode": {"compound": "fieldA", "gene": "fieldB"}}

    renames, removed = _diff_axes(old, new)

    assert renames == {"drug": "compound", "target": "gene"}
    assert removed == []


def test_diff_keeps_axis_when_only_field_changed() -> None:
    """If the name is preserved, the $name selectors are still valid."""
    old = {"explode": {"drug": "fieldA"}}
    new = {"explode": {"drug": "fieldB"}}

    renames, removed = _diff_axes(old, new)

    assert renames == {}
    assert removed == []


def test_rewrite_selector_renames_axis_and_subfield() -> None:
    sel = {"field": "$drug.id", "transform": "as_curie", "args": {"prefix": "x"}}

    new, dropped = _rewrite_selector(sel, {"drug": "compound"}, [])

    assert new["field"] == "$compound.id"
    assert dropped is False


def test_rewrite_selector_flags_removed_axis() -> None:
    sel = {"field": "$drug"}

    new, dropped = _rewrite_selector(sel, {}, ["drug"])

    assert dropped is True


def test_rewrite_selector_atomic_swap() -> None:
    sel = {"field": "$drug", "args": {"fields": ["$target.id", "$drug.id"]}}

    new, dropped = _rewrite_selector(sel, {"drug": "target", "target": "drug"}, [])

    assert dropped is False
    assert new["field"] == "$target"
    assert new["args"]["fields"] == ["$drug.id", "$target.id"]


def test_rewrite_axis_refs_renames_entity_id_and_properties() -> None:
    slot = {
        "id": {"field": "$drug"},
        "properties": {"name": "$drug.name", "static": "literal_field"},
    }

    cleared = _rewrite_axis_refs(slot, {"drug": "compound"}, [])

    assert cleared == []
    assert slot["id"]["field"] == "$compound"
    assert slot["properties"]["name"] == "$compound.name"
    assert slot["properties"]["static"] == "literal_field"


def test_rewrite_axis_refs_clears_endpoints_referencing_removed_axis() -> None:
    slot = {
        "source": {"entity": "drug", "field": "$drug"},
        "target": {"entity": "gene", "field": "geneId"},
        "properties": {"score": "$drug.score", "type": "rel_type"},
    }

    cleared = _rewrite_axis_refs(slot, {}, ["drug"])

    assert "source" not in slot  # cleared — must be re-pointed
    assert slot["target"] == {"entity": "gene", "field": "geneId"}  # untouched
    assert "score" not in slot["properties"]  # property referencing $drug dropped
    assert slot["properties"]["type"] == "rel_type"
    assert "source" in cleared
    assert "properties.score" in cleared


def test_apply_scan_change_noop_when_axes_unchanged() -> None:
    slot = {"id": {"field": "$drug"}, "properties": {}}
    old = {"explode": {"drug": "drugIds"}}
    new = {"explode": {"drug": "drugIds"}}

    _apply_scan_change(slot, old, new)

    assert slot["id"]["field"] == "$drug"


def test_apply_scan_change_rewrites_on_rename() -> None:
    slot = {"id": {"field": "$drug"}, "properties": {"name": "$drug.name"}}
    old = {"explode": {"drug": "drugIds", "target": "targetIds"}}
    new = {"explode": {"compound": "drugIds", "target": "targetIds"}}

    _apply_scan_change(slot, old, new)

    assert slot["id"]["field"] == "$compound"
    assert slot["properties"]["name"] == "$compound.name"
