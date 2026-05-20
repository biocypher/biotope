"""Tests for the add command."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.add import _add_file, _bake_directory, add
from biotope.utils import (
    calculate_file_checksum,
    find_biotope_root,
    is_file_tracked,
    is_git_repo,
    stage_git_changes,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_file(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("This is a test file content")
    return file_path


@pytest.fixture
def biotope_project(tmp_path):
    (tmp_path / ".biotope" / "datasets").mkdir(parents=True)
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture
def git_repo(biotope_project):
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        yield biotope_project


def test_calculate_file_checksum(sample_file):
    import hashlib

    expected_hash = hashlib.sha256(sample_file.read_bytes()).hexdigest()
    assert calculate_file_checksum(sample_file) == expected_hash


def test_find_biotope_root(biotope_project):
    with mock.patch("pathlib.Path.cwd", return_value=biotope_project):
        assert find_biotope_root() == biotope_project

    subdir = biotope_project / "data" / "raw"
    subdir.mkdir(parents=True)
    with mock.patch("pathlib.Path.cwd", return_value=subdir):
        assert find_biotope_root() == biotope_project

    outside_dir = biotope_project.parent / "outside"
    outside_dir.mkdir(exist_ok=True)
    with mock.patch("pathlib.Path.cwd", return_value=outside_dir):
        assert find_biotope_root() is None


def test_is_git_repo(git_repo):
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert is_git_repo(git_repo) is True

        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        assert is_git_repo(git_repo) is False


def test_stage_git_changes(git_repo):
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        stage_git_changes(git_repo)
        mock_run.assert_called_once_with(
            ["git", "add", ".biotope/"],
            cwd=git_repo,
            check=True,
        )


def test_add_file_absolute_path_writes_cr_file_object(git_repo, sample_file):
    target_file = git_repo / sample_file.name
    target_file.write_text(sample_file.read_text())

    datasets_dir = git_repo / ".biotope" / "datasets"
    result = _add_file(target_file, git_repo, datasets_dir, False)
    assert result is True

    metadata_file = datasets_dir / target_file.relative_to(git_repo).with_suffix(".jsonld")
    assert metadata_file.exists()

    with open(metadata_file) as handle:
        metadata = json.load(handle)

    assert metadata["distribution"][0]["@type"] == "cr:FileObject"
    assert metadata["distribution"][0]["contentUrl"] == str(target_file.relative_to(git_repo))
    assert is_file_tracked(target_file, git_repo)


def test_add_file_relative_path_already_tracked(git_repo):
    data_dir = git_repo / "data" / "raw"
    data_dir.mkdir(parents=True)
    target_file = data_dir / "experiment.csv"
    target_file.write_text("gene,expression\nBRCA1,12.5")

    datasets_dir = git_repo / ".biotope" / "datasets"

    original_cwd = Path.cwd()
    try:
        os.chdir(git_repo)
        relative_path = Path("data/raw/experiment.csv")
        assert _add_file(relative_path, git_repo, datasets_dir, False) is True
        assert _add_file(relative_path, git_repo, datasets_dir, False) is False
        assert _add_file(relative_path, git_repo, datasets_dir, True) is True
    finally:
        os.chdir(original_cwd)


def test_dedupe_file_objects_covered_by_filesets(tmp_path):
    """Regression: baker emits FileSet + per-file FileObjects; keep only the FileSet."""
    from biotope.commands.add import _dedupe_file_objects_covered_by_filesets

    project_root = tmp_path / "project"
    data_dir = project_root / "data" / "partitions"
    data_dir.mkdir(parents=True)
    (project_root / ".biotope" / "datasets").mkdir(parents=True)
    (data_dir / "part-00.parquet").write_bytes(b"x")
    (data_dir / "part-01.parquet").write_bytes(b"y")
    (data_dir / "_SUCCESS").write_text("")

    metadata = {
        "distribution": [
            {"@type": "cr:FileSet", "@id": "fs", "includes": "*.parquet"},
            {"@type": "cr:FileObject", "@id": "fo1", "contentUrl": "part-00.parquet"},
            {"@type": "cr:FileObject", "@id": "fo2", "contentUrl": "part-01.parquet"},
            {"@type": "cr:FileObject", "@id": "fo3", "contentUrl": "data/partitions/_SUCCESS"},
        ]
    }
    _dedupe_file_objects_covered_by_filesets(metadata, data_dir, project_root)

    types = [(d.get("@type"), d.get("@id")) for d in metadata["distribution"]]
    assert ("cr:FileSet", "fs") in types
    assert ("cr:FileObject", "fo3") in types  # genuinely uncovered survives
    assert ("cr:FileObject", "fo1") not in types
    assert ("cr:FileObject", "fo2") not in types


def test_bake_directory_tracks_unparseable_files(tmp_path):
    project_root = tmp_path / "project"
    data_dir = project_root / "data" / "mixed"
    (project_root / ".biotope" / "datasets").mkdir(parents=True)
    data_dir.mkdir(parents=True)

    source_csv = Path("tests/example_gene_expression.csv").resolve()
    (data_dir / "example_gene_expression.csv").write_text(source_csv.read_text())
    (data_dir / "README.md").write_text("notes")

    metadata_dict, n_source_files = _bake_directory(data_dir, project_root, {})

    assert n_source_files == 2
    assert metadata_dict["recordSet"]
    distribution = metadata_dict["distribution"]
    assert any(item["@type"] == "cr:FileObject" for item in distribution)
    assert any(item.get("contentUrl") == "data/mixed/README.md" for item in distribution)

    scaffold_path = data_dir / ".biotope.yaml"
    from biotope.commands.add import _generate_biotope_scaffold_from_baked
    import yaml

    _generate_biotope_scaffold_from_baked(data_dir, metadata_dict, project_root)
    assert scaffold_path.exists()
    payload = yaml.safe_load(scaffold_path.read_text())
    assert isinstance(payload, dict)
    assert isinstance(payload["dataset"], dict)
    assert payload["dataset"]["source_path"] == "data/mixed"
    assert isinstance(payload["record_sets"], list)
    assert payload["record_sets"]


@mock.patch("biotope.commands.add.find_biotope_root")
@mock.patch("biotope.commands.add.is_git_repo")
@mock.patch("biotope.commands.add._bake_directory")
@mock.patch("biotope.commands.add._generate_biotope_scaffold_from_baked")
@mock.patch("biotope.commands.add.stage_git_changes")
def test_add_command_directory_recurses_by_default(
    mock_stage,
    mock_csv,
    mock_bake,
    mock_is_git,
    mock_find_root,
    runner,
    git_repo,
):
    mock_find_root.return_value = git_repo
    mock_is_git.return_value = True

    data_dir = git_repo / "data"
    data_dir.mkdir()
    fake_metadata = {"recordSet": [{"@id": "#rs", "field": []}], "distribution": []}
    mock_bake.return_value = (fake_metadata, 2)

    with runner.isolated_filesystem():
        os.chdir(git_repo)
        result = runner.invoke(add, [str(data_dir)])

    assert result.exit_code == 0
    mock_bake.assert_called_once()
    mock_stage.assert_called_once_with(git_repo)
    mock_csv.assert_called_once()


@mock.patch("biotope.commands.add.find_biotope_root")
@mock.patch("biotope.commands.add.is_git_repo")
@mock.patch("biotope.commands.add._bake_directory")
@mock.patch("biotope.commands.add._generate_biotope_scaffold_from_baked")
@mock.patch("biotope.commands.add.stage_git_changes")
def test_add_command_resolves_relative_directory(
    mock_stage,
    mock_csv,
    mock_bake,
    mock_is_git,
    mock_find_root,
    runner,
    git_repo,
):
    """Regression: relative dir argument must not break CSV scaffold writing."""
    mock_find_root.return_value = git_repo
    mock_is_git.return_value = True

    (git_repo / "data").mkdir()
    fake_metadata = {"recordSet": [], "distribution": []}
    mock_bake.return_value = (fake_metadata, 1)

    os.chdir(git_repo)
    result = runner.invoke(add, ["data"])

    assert result.exit_code == 0, result.output
    csv_source_dir = mock_csv.call_args.args[0]
    assert csv_source_dir.is_absolute()
    assert csv_source_dir == (git_repo / "data").resolve()


@mock.patch("biotope.commands.add.find_biotope_root")
@mock.patch("biotope.commands.add.is_git_repo")
def test_add_command_rejects_name_for_multiple_paths(mock_is_git, mock_find_root, runner, git_repo):
    mock_find_root.return_value = git_repo
    mock_is_git.return_value = True

    file_one = git_repo / "one.txt"
    file_two = git_repo / "two.txt"
    file_one.write_text("one")
    file_two.write_text("two")

    with runner.isolated_filesystem():
        os.chdir(git_repo)
        result = runner.invoke(add, ["--name", "dataset", str(file_one), str(file_two)])

    assert result.exit_code != 0
    assert "--name can only be used when adding one path" in result.output
