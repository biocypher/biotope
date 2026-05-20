"""Tests for the deterministic inspector service."""
from __future__ import annotations

import json
from pathlib import Path

from biotope.croissant.mapping import inspect_dataset, render_inspection_text
from biotope.croissant.spec import load_from_path


def test_inspector_lists_record_sets_and_fields(minimal_croissant: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    inspection = inspect_dataset(dataset, datasets_location=None, preview_rows=0)
    assert inspection.name is not None
    names = [rs.name for rs in inspection.record_sets]
    assert "genes" in names
    genes = inspection.by_name("genes")
    assert genes is not None
    field_names = [f.name for f in genes.fields]
    assert "ensembl_id" in field_names
    assert "ensembl_id" in genes.identifier_like_fields


def test_inspector_classifies_field_kinds(two_recordsets_croissant: Path) -> None:
    dataset = load_from_path(two_recordsets_croissant)
    inspection = inspect_dataset(dataset, datasets_location=None, preview_rows=0)
    fields = {f.name: f for f in inspection.by_name("gene_disease").fields}
    assert fields["score"].kind == "float"
    assert fields["gene_id"].is_identifier_like


def test_inspector_json_output_is_stable(minimal_croissant: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    inspection = inspect_dataset(dataset, datasets_location=None, preview_rows=0)
    payload = inspection.to_json()
    serialised = json.dumps(payload, sort_keys=True)
    # Must round-trip JSON cleanly
    assert json.loads(serialised) == payload


def test_inspector_text_renders_samples_as_kv_blocks(
    minimal_croissant: Path,
    gene_csv: Path,
    tmp_path: Path,
) -> None:
    croissant_path = tmp_path / "minimal.croissant.json"
    croissant_path.write_text(minimal_croissant.read_text())
    (tmp_path / "genes.csv").write_text(gene_csv.read_text())

    dataset = load_from_path(croissant_path)
    inspection = inspect_dataset(dataset, datasets_location=tmp_path, preview_rows=2)
    text = render_inspection_text(inspection)
    # Vertical key:value layout
    assert "row 1:" in text
    assert "ensembl_id:" in text
    # Did not collapse into a horizontal table
    assert "BRCA2" in text


def test_inspector_handles_missing_data_gracefully(minimal_croissant: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    inspection = inspect_dataset(dataset, datasets_location=None, preview_rows=3)
    genes = inspection.by_name("genes")
    assert genes.sample_rows == []
    assert genes.sample_note is not None
