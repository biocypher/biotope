"""Tests for axis-edit diff and selector rewriting in the wizard."""

from __future__ import annotations

from biotope.commands.map_wizard import (
    _apply_scan_change,
    _rewrite_selector,
)


def test_rewrite_selector_atomic_swap() -> None:
    sel = {"field": "$drug", "args": {"fields": ["$target.id", "$drug.id"]}}

    new, dropped = _rewrite_selector(sel, {"drug": "target", "target": "drug"}, [])

    assert dropped is False
    assert new["field"] == "$target"
    assert new["args"]["fields"] == ["$drug.id", "$target.id"]


def test_scan_edit_applies_paired_renames_and_preserves_other_fields():
    slot = {
        "id": {"field": "$drug.id", "transform": "as_curie", "args": {"prefix": "x"}},
        "properties": {"name": "$target.name", "static": "literal_field"},
    }
    _apply_scan_change(
        slot, {"explode": {"drug": "fieldA", "target": "fieldB"}}, {"explode": {"compound": "fieldA", "gene": "fieldB"}}
    )
    assert slot["id"] == {"field": "$compound.id", "transform": "as_curie", "args": {"prefix": "x"}}
    assert slot["properties"] == {"name": "$gene.name", "static": "literal_field"}


def test_scan_edit_collapses_axis_and_clears_removed_bindings():
    slot = {
        "source": {"entity": "drug", "field": "$drug"},
        "target": {"entity": "gene", "field": "$target"},
        "properties": {"score": "$target.score", "type": "rel_type"},
    }
    _apply_scan_change(slot, {"explode": {"drug": "drugIds", "target": "targetIds"}}, {"explode": "drugIds"})
    assert slot["source"] == {"entity": "drug", "field": "$item"}
    assert "target" not in slot
    assert slot["properties"] == {"type": "rel_type"}


def test_scan_edit_keeps_bindings_when_names_stay():
    slot = {"id": {"field": "$drug"}, "properties": {}}
    old = {"explode": {"drug": "fieldA"}}
    _apply_scan_change(slot, old, old)
    assert slot == {"id": {"field": "$drug"}, "properties": {}}
    _apply_scan_change(slot, old, {"explode": {"drug": "fieldB"}})
    assert slot == {"id": {"field": "$drug"}, "properties": {}}
