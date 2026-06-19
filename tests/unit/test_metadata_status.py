"""Tests for the biotope:status + prov:wasDerivedFrom helpers in metadata.py."""

from __future__ import annotations

import pytest

from biotope.metadata import (
    STATUS_MAPPED,
    STATUS_PROCESSED,
    STATUS_RAW,
    add_derived_from,
    classify_status_from_baker,
    get_derived_from,
    get_status,
    merge_metadata,
    normalize_metadata_shape,
    set_status,
)


def test_legacy_manifest_defaults_to_raw():
    """A manifest with no `biotope:status` field is treated as raw."""
    assert get_status({}) == STATUS_RAW
    assert get_status({"name": "x"}) == STATUS_RAW


def test_set_status_roundtrip():
    metadata: dict = {}
    set_status(metadata, STATUS_PROCESSED)
    assert metadata["biotope:status"] == STATUS_PROCESSED
    assert get_status(metadata) == STATUS_PROCESSED
    set_status(metadata, STATUS_MAPPED)
    assert get_status(metadata) == STATUS_MAPPED


def test_set_status_rejects_bad_value():
    with pytest.raises(ValueError, match="invalid status"):
        set_status({}, "wat")


def test_classify_processed_when_recordset_has_fields():
    metadata = {
        "recordSet": [
            {"@id": "#rs", "field": [{"name": "x"}]},
        ],
    }
    assert classify_status_from_baker(metadata) == STATUS_PROCESSED


def test_classify_raw_when_recordset_empty_or_fieldless():
    assert classify_status_from_baker({"recordSet": []}) == STATUS_RAW
    assert classify_status_from_baker({"recordSet": [{"@id": "#rs"}]}) == STATUS_RAW
    assert classify_status_from_baker({"recordSet": [{"@id": "#rs", "field": []}]}) == STATUS_RAW
    assert classify_status_from_baker({}) == STATUS_RAW


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


def test_merge_metadata_includes_biotope_and_prov_namespaces():
    """Every manifest biotope writes must carry the new namespaces so
    downstream tools can interpret `biotope:status` and
    `prov:wasDerivedFrom`."""
    ctx = merge_metadata({})["@context"]
    assert ctx["biotope"].startswith("https://")
    assert ctx["prov"] == "http://www.w3.org/ns/prov#"


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
