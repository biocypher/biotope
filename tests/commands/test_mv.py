"""Core tests for biotope mv — multi-file cases live in test_mv_multifile.py."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner

from biotope.commands.mv import (
    _find_metadata_files_for_file,
    _resolve_destination_path,
    _update_metadata_file_path,
    _validate_move_operation,
    mv,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def biotope_project_with_file(tmp_path):
    biotope_dir = tmp_path / ".biotope"
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    (tmp_path / ".git").mkdir()

    data_dir = tmp_path / "data" / "inputs"
    data_dir.mkdir(parents=True)
    test_file = data_dir / "test.csv"
    test_file.write_text("gene,expression\nBRCA1,12.5")

    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "test",
        "description": "Dataset for test.csv",
        "distribution": [
            {
                "@type": "cr:FileObject",
                "@id": "file_12345678",
                "name": "test.csv",
                "contentUrl": "data/inputs/test.csv",
                "sha256": "abc123",
                "contentSize": 100,
                "dateCreated": "2023-01-01T00:00:00Z",
            }
        ],
    }
    metadata_dir = datasets_dir / "data" / "inputs"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "test.csv.jsonld").write_text(json.dumps(metadata, indent=2))
    return tmp_path


def test_find_and_update_metadata(biotope_project_with_file):
    test_file = biotope_project_with_file / "data" / "inputs" / "test.csv"
    metadata_files = _find_metadata_files_for_file(test_file, biotope_project_with_file)
    assert len(metadata_files) == 1

    dest_dir = biotope_project_with_file / "data" / "outputs"
    dest_dir.mkdir(parents=True)
    dest_file = dest_dir / "test.csv"
    dest_file.write_text("gene,expression\nBRCA1,12.5")

    metadata_file = metadata_files[0]
    assert _update_metadata_file_path(
        metadata_file, "data/inputs/test.csv", "data/outputs/test.csv", "new_checksum_123", biotope_project_with_file
    )

    updated = json.loads(metadata_file.read_text())
    assert updated["distribution"][0]["contentUrl"] == "data/outputs/test.csv"
    assert updated["distribution"][0]["sha256"] == "new_checksum_123"


@pytest.mark.parametrize(
    "setup,message",
    [
        ("outside_dest", "outside biotope project"),
        ("same_path", "Source and destination are the same"),
        ("biotope_internal", "biotope internal"),
    ],
)
def test_validate_move_operation_rejects(biotope_project, setup, message):
    source = biotope_project / "data" / "file.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("x")

    if setup == "outside_dest":
        destination = biotope_project.parent / "outside.txt"
    elif setup == "same_path":
        destination = source
    else:
        source = biotope_project / ".biotope" / "config.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("config")
        destination = biotope_project / ".biotope" / "moved.yaml"

    with pytest.raises(click.Abort):
        _validate_move_operation(source, destination, biotope_project, force=False)


@pytest.mark.parametrize(
    "dest_input,expected_name",
    [
        ("/tmp/existing_dir", "file.txt"),
        ("/tmp/new/path/file.txt", "file.txt"),
        ("/tmp/existing.txt", "existing.txt"),
    ],
)
def test_resolve_destination_path(dest_input, expected_name, tmp_path):
    source = tmp_path / "file.txt"
    source.write_text("content")
    dest = Path(dest_input.replace("/tmp", str(tmp_path)))
    if dest.suffix:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("existing")
    else:
        dest.mkdir(parents=True, exist_ok=True)
    resolved = _resolve_destination_path(source, dest)
    assert resolved.name == expected_name


def test_mv_not_in_biotope_project(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(mv, ["a.txt", "b.txt"])
    assert result.exit_code != 0


def test_mv_file_not_tracked(runner, biotope_project):
    source = biotope_project / "test.csv"
    source.write_text("x")
    with runner.isolated_filesystem(temp_dir=biotope_project):
        with mock.patch("biotope.commands.mv.is_file_tracked", return_value=False):
            result = runner.invoke(mv, [str(source), "moved.csv"])
    assert result.exit_code != 0
    assert "is not tracked" in result.output


def test_mv_successful_move(runner, biotope_project_with_file):
    source_file = biotope_project_with_file / "data" / "inputs" / "test.csv"
    destination = biotope_project_with_file / "data" / "outputs" / "test.csv"
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        result = runner.invoke(mv, [str(source_file), str(destination)])
        assert result.exit_code == 0
        assert "Move Complete" in result.output
        assert not source_file.exists()
        assert destination.exists()
        metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "outputs" / "test.csv.jsonld"
        assert json.loads(metadata_file.read_text())["distribution"][0]["contentUrl"] == "data/outputs/test.csv"
    finally:
        os.chdir(original_cwd)


def test_mv_force_overwrite(runner, biotope_project_with_file):
    source_file = biotope_project_with_file / "data" / "inputs" / "test.csv"
    destination = biotope_project_with_file / "data" / "outputs" / "existing.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("existing content")
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        result = runner.invoke(mv, [str(source_file), str(destination), "--force"])
        assert result.exit_code == 0
        assert destination.read_text() == "gene,expression\nBRCA1,12.5"
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_metadata_file_move_failure(runner, biotope_project_with_file):
    source_file = biotope_project_with_file / "data" / "inputs" / "test.csv"
    destination = biotope_project_with_file / "data" / "outputs" / "test.csv"
    original_cwd = Path.cwd()
    original_move = shutil.move

    def mock_move_side_effect(src, dst):
        if "test.csv.jsonld" in str(src):
            raise OSError("Metadata move failed")
        return original_move(src, dst)

    try:
        os.chdir(biotope_project_with_file)
        with mock.patch("biotope.commands.mv.shutil.move", side_effect=mock_move_side_effect):
            result = runner.invoke(mv, [str(source_file), str(destination)])
        assert result.exit_code != 0
        assert "Failed to move metadata file" in result.output
        assert source_file.exists()
        assert not destination.exists()
    finally:
        os.chdir(original_cwd)


def baked(tmp_path, monkeypatch):
    from biotope.cli import cli

    runner = CliRunner()
    assert runner.invoke(cli, ["init", "baked", "--dir", str(tmp_path), "--no-prompt"]).exit_code == 0
    root = tmp_path / "baked"
    monkeypatch.chdir(root)
    shutil.copytree(Path(__file__).resolve().parents[1] / "fixtures/things", root / "data/things")
    (root / "data/solo").mkdir()
    (root / "data/solo/only.csv").write_text("id\n1\n")
    added = runner.invoke(cli, ["add", "data/things", "data/solo"])
    assert added.exit_code == 0, added.output
    return root, lambda *args: runner.invoke(cli, list(args))


def described(root, dataset):
    manifest = json.loads((root / f".biotope/datasets/{dataset}.jsonld").read_text())
    return {entry["contentUrl"] for entry in manifest["distribution"]}, manifest


def test_mv_accepts_files_baker_described_in_a_folder_manifest(tmp_path, monkeypatch):
    from biotope.utils import is_file_tracked

    root, run = baked(tmp_path, monkeypatch)
    assert described(root, "data/things")[0] == {"first.csv", "second.csv"}
    moved = run("mv", "data/things/first.csv", "data/things/renamed.csv")
    assert moved.exit_code == 0, moved.output
    assert described(root, "data/things")[0] == {"renamed.csv", "second.csv"}
    assert is_file_tracked(root / "data/things/renamed.csv", root)
    alone = run("mv", "data/solo/only.csv", "data/solo/single.csv")
    assert alone.exit_code == 0, alone.output
    assert described(root, "data/solo")[0] == {"single.csv"}
    assert sorted(path.name for path in (root / ".biotope/datasets/data").iterdir()) == ["solo.jsonld", "things.jsonld"]
