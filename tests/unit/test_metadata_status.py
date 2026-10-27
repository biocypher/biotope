"""Tests for the biotope:status + prov:wasDerivedFrom helpers in metadata.py."""

from __future__ import annotations

from biotope.metadata import (
    STATUS_RAW,
    add_derived_from,
    get_derived_from,
    get_status,
    normalize_metadata_shape,
)


def test_legacy_manifest_defaults_to_raw():
    """A manifest with no `biotope:status` field is treated as raw."""
    assert get_status({}) == STATUS_RAW
    assert get_status({"name": "x"}) == STATUS_RAW


def test_get_derived_from_handles_all_shapes():
    """JSON-LD lets us write a single object, a single string, or a list."""
    assert get_derived_from({}) == []
    assert get_derived_from({"prov:wasDerivedFrom": "pdf_1"}) == ["pdf_1"]
    assert get_derived_from({"prov:wasDerivedFrom": {"@id": "pdf_1"}}) == ["pdf_1"]
    assert get_derived_from({"prov:wasDerivedFrom": [{"@id": "pdf_1"}, {"@id": "pdf_2"}]}) == ["pdf_1", "pdf_2"]


def test_add_derived_from_is_idempotent():
    metadata: dict = {}
    add_derived_from(metadata, "pdf_1")
    add_derived_from(metadata, "pdf_2")
    add_derived_from(metadata, "pdf_1")  # duplicate
    assert get_derived_from(metadata) == ["pdf_1", "pdf_2"]


def test_normalize_metadata_shape_coerces_singleton_field_and_subfield() -> None:
    metadata = {
        "recordSet": [
            {
                "@id": "#rs",
                "name": "genes",
                "field": {
                    "name": "authors",
                    "subField": {"name": "name", "dataType": "sc:Text"},
                },
            },
        ],
    }
    normalized = normalize_metadata_shape(metadata)
    field = normalized["recordSet"][0]["field"]
    assert isinstance(field, list)
    assert isinstance(field[0]["subField"], list)
