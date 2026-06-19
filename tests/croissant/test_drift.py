"""Tests for manifest-drift detection (data edited after a Croissant bake)."""

from __future__ import annotations

import os
import time
from pathlib import Path

from biotope.croissant.acquisition import detect_manifest_drift


def test_no_drift_when_data_predates_manifest_or_inputs_missing(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    data_file = data_dir / "genes.csv"
    data_file.write_text("id,symbol\n1,A\n")

    croissant_path = tmp_path / "dataset.jsonld"
    croissant_path.write_text("{}")
    # Ensure the manifest is unambiguously newer.
    future = time.time() + 10
    os.utime(croissant_path, (future, future))

    assert detect_manifest_drift(croissant_path, data_dir) == []
    assert detect_manifest_drift(tmp_path / "missing.jsonld", data_dir) == []
    assert detect_manifest_drift(croissant_path, tmp_path / "missing-dir") == []


def test_drift_detected_when_data_newer_than_manifest(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    croissant_path = tmp_path / "dataset.jsonld"
    croissant_path.write_text("{}")

    data_file = data_dir / "genes.csv"
    future = time.time() + 10
    data_file.write_text("id,symbol\n1,A\n")
    os.utime(data_file, (future, future))

    drifted = detect_manifest_drift(croissant_path, data_dir)
    assert drifted == [data_file]
