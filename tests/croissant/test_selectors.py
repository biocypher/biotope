"""Tests for the selector resolver and value-level transforms."""

from __future__ import annotations

import pytest

from biotope.croissant.acquisition.context import RecordRow
from biotope.croissant.mapping import Selector
from biotope.croissant.mapping.selectors import ResolutionContext, resolve_selector


def _ctx(values: dict | None = None, *, item=None, ids=None) -> ResolutionContext:
    items = {"item": item} if item is not None else None
    return ResolutionContext(row=RecordRow(record_set="rs", values=values or {}), items=items, ids=ids)


def test_passthrough_returns_field_value() -> None:
    ctx = _ctx({"x": "hello"})
    assert resolve_selector(Selector(field="x"), ctx) == "hello"


def test_as_curie_prepends_prefix() -> None:
    sel = Selector(field="id", transform="as_curie", args={"prefix": "ensembl"})
    assert resolve_selector(sel, _ctx({"id": "ENSG1"})) == "ensembl:ENSG1"


def test_as_curie_returns_none_on_missing() -> None:
    sel = Selector(field="id", transform="as_curie", args={"prefix": "ensembl"})
    assert resolve_selector(sel, _ctx({"id": None})) is None
    assert resolve_selector(sel, _ctx({"id": ""})) is None


def test_hash_id_uses_all_fields() -> None:
    sel = Selector(transform="hash_id", args={"fields": ["a", "b"], "prefix": "h"})
    assert resolve_selector(sel, _ctx({"a": "1", "b": "2"})).startswith("h:")


def test_hash_id_short_circuits_on_missing() -> None:
    sel = Selector(transform="hash_id", args={"fields": ["a", "b"]})
    assert resolve_selector(sel, _ctx({"a": "1"})) is None


def test_use_resolves_through_ids_table() -> None:
    ids = {"gene_curie": Selector(field="id", transform="as_curie", args={"prefix": "ensembl"})}
    sel = Selector(use="gene_curie")
    assert resolve_selector(sel, _ctx({"id": "ENSG1"}, ids=ids)) == "ensembl:ENSG1"


def test_item_resolves_against_current_array_element() -> None:
    sel = Selector(field="$item.disease_id")
    ctx = _ctx({"x": 1}, item={"disease_id": "D1"})
    assert resolve_selector(sel, ctx) == "D1"


def test_bare_item_returns_whole_element() -> None:
    sel = Selector(field="$item")
    ctx = _ctx({}, item="A")
    assert resolve_selector(sel, ctx) == "A"


def test_as_curie_refuses_array_value() -> None:
    """Stringifying a list into a CURIE would produce garbage like `ensembl:['A','B']`."""
    sel = Selector(field="x", transform="as_curie", args={"prefix": "ensembl"})
    assert resolve_selector(sel, _ctx({"x": ["A", "B"]})) is None


def test_unknown_transform_raises() -> None:
    sel = Selector(field="x", transform="not_a_thing")
    with pytest.raises(KeyError):
        resolve_selector(sel, _ctx({"x": "y"}))
