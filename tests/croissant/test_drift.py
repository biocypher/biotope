"""Tests for manifest-drift detection (data edited after a Croissant bake)."""

from __future__ import annotations

import os
import time
from pathlib import Path

from biotope.croissant.acquisition import detect_manifest_drift
from biotope.metadata import SCAFFOLD_FILENAME


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


def test_scaffold_file_is_not_drift(tmp_path: Path) -> None:
    """``biotope add`` writes ``.biotope.yaml`` right after baking the manifest,
    so it is always newer than the manifest by construction. It must not be
    reported as drift, or every ``add`` would falsely warn."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    croissant_path = tmp_path / "dataset.jsonld"
    croissant_path.write_text("{}")

    data_file = data_dir / "genes.csv"
    past = time.time() - 10
    data_file.write_text("id,symbol\n1,A\n")
    os.utime(data_file, (past, past))

    scaffold_file = data_dir / SCAFFOLD_FILENAME
    future = time.time() + 10
    scaffold_file.write_text("name: genes\n")
    os.utime(scaffold_file, (future, future))

    assert detect_manifest_drift(croissant_path, data_dir) == []

    # Real drift on the data file itself must still be detected.
    os.utime(data_file, (future, future))
    assert detect_manifest_drift(croissant_path, data_dir) == [data_file]
