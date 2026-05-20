"""Tests for the check-data command."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from biotope.commands.check_data import check_data


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tracked_project(tmp_path):
    project_root = tmp_path
    (project_root / ".git").mkdir()
    datasets_dir = project_root / ".biotope" / "datasets" / "data" / "raw"
    datasets_dir.mkdir(parents=True)
    data_file = project_root / "data" / "raw" / "test.csv"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text("gene,expression\nBRCA1,12.5")

    import hashlib

    checksum = hashlib.sha256(data_file.read_bytes()).hexdigest()
    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "test",
        "distribution": [
            {
                "@type": "cr:FileObject",
                "@id": "file_1",
                "name": "test.csv",
                "contentUrl": "data/raw/test.csv",
                "sha256": checksum,
            }
        ],
    }
    metadata_path = datasets_dir / "test.jsonld"
    metadata_path.write_text(json.dumps(metadata, indent=2))
    return project_root, metadata_path


def test_check_data_valid_file(runner, tracked_project):
    project_root, _metadata_path = tracked_project
    original_cwd = Path.cwd()
    try:
        os.chdir(project_root)
        result = runner.invoke(check_data, [])
    finally:
        os.chdir(original_cwd)

    assert result.exit_code == 0
    assert "VALID" in result.output


def test_check_data_rejects_legacy_file_objects(runner, tracked_project):
    project_root, metadata_path = tracked_project
    metadata = json.loads(metadata_path.read_text())
    metadata["distribution"][0]["@type"] = "sc:FileObject"
    metadata_path.write_text(json.dumps(metadata, indent=2))

    original_cwd = Path.cwd()
    try:
        os.chdir(project_root)
        result = runner.invoke(check_data, [])
    finally:
        os.chdir(original_cwd)

    assert result.exit_code != 0
    assert "Legacy sc:FileObject is no longer supported" in result.output
