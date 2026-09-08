"""Tests for manifest-drift detection (data edited after a Croissant bake)."""

from __future__ import annotations

import os
from pathlib import Path

from biotope.croissant.acquisition import detect_manifest_drift
from biotope.metadata import SCAFFOLD_FILENAME


def test_managed_directory_drift_ignores_scaffold_and_missing_inputs(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    data_file = data_dir / "genes.csv"
    data_file.write_text("id,symbol\n1,A\n")

    croissant_path = tmp_path / ".biotope" / "datasets" / "data.jsonld"
    croissant_path.parent.mkdir(parents=True)
    croissant_path.write_text("{}")
    os.utime(data_file, (100, 100))
    os.utime(croissant_path, (200, 200))

    scaffold = data_dir / SCAFFOLD_FILENAME
    scaffold.write_text("name: genes\n")
    os.utime(scaffold, (300, 300))

    assert detect_manifest_drift(croissant_path, data_dir) == []
    assert detect_manifest_drift(tmp_path / "missing.jsonld", data_dir) == []
    assert detect_manifest_drift(croissant_path, tmp_path / "missing-dir") == []

    # Real drift on the data file itself must still be detected.
    os.utime(data_file, (300, 300))
    assert detect_manifest_drift(croissant_path, data_dir) == [data_file]


def test_single_file_manifest_only_checks_its_declared_payload(tmp_path: Path) -> None:
    import json

    source = tmp_path / "raw" / "study.xlsx"
    source.parent.mkdir()
    source.write_bytes(b"not opened by this timestamp check")
    manifest = tmp_path / ".biotope" / "datasets" / "raw" / "study.jsonld"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"distribution": [{"@type": "cr:FileObject", "contentUrl": "raw/study.xlsx"}]}))
    os.utime(source, (100, 100))
    os.utime(manifest, (200, 200))
    (tmp_path / "new.mapping.yaml").write_text("unrelated")
    assert detect_manifest_drift(manifest, tmp_path) == []
    os.utime(source, (300, 300))
    assert detect_manifest_drift(manifest, tmp_path) == [source]


def test_unmanaged_manifests_do_not_claim_rebake_drift(tmp_path):
    manifest = tmp_path / "handwritten.jsonld"
    manifest.write_text("{}")
    sibling = tmp_path / "another.jsonld"
    sibling.write_text("{}")
    os.utime(manifest, (100, 100))
    os.utime(sibling, (200, 200))
    assert detect_manifest_drift(manifest, tmp_path) == []
