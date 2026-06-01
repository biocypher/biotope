"""Tests for the biotope:status + prov:wasDerivedFrom helpers in metadata.py."""

from __future__ import annotations

import pytest

from biotope.metadata import (
    FETCHED_AT_KEY,
    SOURCE_KEY,
    STATUS_MAPPED,
    STATUS_PROCESSED,
    STATUS_RAW,
    add_derived_from,
    classify_status_from_baker,
    get_derived_from,
    get_source,
    get_status,
    merge_metadata,
    set_source,
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


def test_set_source_records_origin_and_timestamp():
    """`biotope get` stamps where data came from + when it was fetched."""
    metadata: dict = {}
    set_source(metadata, "https://example.com/data.csv", "2026-06-01T00:00:00+00:00")
    assert metadata[SOURCE_KEY] == "https://example.com/data.csv"
    assert metadata[FETCHED_AT_KEY] == "2026-06-01T00:00:00+00:00"
    assert get_source(metadata) == "https://example.com/data.csv"


def test_set_source_leaves_clean_when_empty():
    """Plain `biotope add` (no external origin) must not add ingress fields."""
    metadata: dict = {}
    set_source(metadata, None)
    assert SOURCE_KEY not in metadata
    assert FETCHED_AT_KEY not in metadata
    assert get_source(metadata) is None


def test_set_source_without_timestamp():
    metadata: dict = {}
    set_source(metadata, "/scratch/data/foo.csv")
    assert metadata[SOURCE_KEY] == "/scratch/data/foo.csv"
    assert FETCHED_AT_KEY not in metadata


def test_get_source_accepts_node_form():
    assert get_source({SOURCE_KEY: {"@id": "https://e.com/x"}}) == "https://e.com/x"
    assert get_source({}) is None
