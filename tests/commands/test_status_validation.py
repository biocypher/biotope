"""Status command annotation validation display."""

from __future__ import annotations

import json
import os
from unittest import mock

import pytest
import yaml
from click.testing import CliRunner

from biotope.commands.status import status
from tests.conftest import ANNOTATION_VALIDATION_CONFIG


@pytest.fixture
def runner():
    return CliRunner()


def _write_config(git_repo):
    config_file = git_repo / ".biotope" / "config.yaml"
    config_file.write_text(yaml.dump(ANNOTATION_VALIDATION_CONFIG))


def _write_metadata(git_repo, name: str, *, complete: bool):
    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": name,
        "description": "Dataset for experiment3.csv" if not complete else "Dataset for experiment3.csv with complete annotation",
        "distribution": [
            {
                "@type": "cr:FileObject",
                "@id": "file_e3b0c442",
                "name": "experiment3.csv",
                "contentUrl": "data/inputs/experiment3.csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "contentSize": 0,
                "dateCreated": "2025-07-15T14:57:55.699579+00:00",
            }
        ],
    }
    if complete:
        metadata["creator"] = {"name": "John Doe", "email": "john@example.com"}
        metadata["dateCreated"] = "2025-07-15T14:57:55.699579+00:00"
    metadata_file = git_repo / ".biotope" / "datasets" / f"{name}.jsonld"
    metadata_file.write_text(json.dumps(metadata))


@pytest.mark.parametrize("complete,expected_fragment", [(False, "Incomplete"), (True, "Valid")])
def test_status_annotation_display(runner, git_repo, complete, expected_fragment):
    _write_config(git_repo)
    _write_metadata(git_repo, "experiment3", complete=complete)
    with (
        mock.patch("biotope.utils.find_biotope_root", return_value=git_repo),
        mock.patch(
            "biotope.commands.status._get_git_status", return_value={"staged": [], "modified": [], "untracked": []}
        ),
    ):
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            result = runner.invoke(status)
    assert result.exit_code == 0
    assert "experiment3" in result.output
    assert expected_fragment in result.output


@pytest.mark.parametrize(
    "staged,expect_suggest",
    [(True, True), (False, True)],
)
def test_status_suggests_annotate_when_incomplete(runner, git_repo, staged, expect_suggest):
    _write_config(git_repo)
    _write_metadata(git_repo, "experiment3", complete=False)
    git_status = {"staged": [], "modified": [], "untracked": []}
    if staged:
        git_status["staged"] = [("A", ".biotope/datasets/experiment3.jsonld")]

    with (
        mock.patch("biotope.utils.find_biotope_root", return_value=git_repo),
        mock.patch("biotope.commands.status._get_git_status", return_value=git_status),
        mock.patch("subprocess.run") as mock_subprocess,
    ):
        if staged:
            mock_subprocess.return_value.returncode = 0
            mock_subprocess.return_value.stdout = ".biotope/datasets/experiment3.jsonld\n"
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            result = runner.invoke(status)

    assert result.exit_code == 0
    if expect_suggest:
        assert "biotope annotate edit" in result.output


def test_status_no_annotate_suggestion_when_complete_staged(runner, git_repo):
    _write_config(git_repo)
    _write_metadata(git_repo, "experiment3", complete=True)
    with (
        mock.patch("biotope.utils.find_biotope_root", return_value=git_repo),
        mock.patch(
            "biotope.commands.status._get_git_status",
            return_value={"staged": [("A", ".biotope/datasets/experiment3.jsonld")], "modified": [], "untracked": []},
        ),
        mock.patch("subprocess.run") as mock_subprocess,
    ):
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ".biotope/datasets/experiment3.jsonld\n"
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            result = runner.invoke(status)
    assert result.exit_code == 0
    assert "biotope annotate edit --staged" not in result.output


def test_status_detailed_shows_validation_errors(runner, git_repo):
    _write_config(git_repo)
    _write_metadata(git_repo, "experiment3", complete=False)
    with (
        mock.patch("biotope.utils.find_biotope_root", return_value=git_repo),
        mock.patch(
            "biotope.commands.status._get_git_status", return_value={"staged": [], "modified": [], "untracked": []}
        ),
    ):
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            result = runner.invoke(status, ["--detailed"])
    assert result.exit_code == 0
    assert "Validation Issues" in result.output or "creator" in result.output.lower()


def test_status_skips_validation_when_disabled(runner, git_repo):
    config = {"annotation_validation": {"enabled": False}}
    (git_repo / ".biotope" / "config.yaml").write_text(yaml.dump(config))
    _write_metadata(git_repo, "experiment3", complete=False)
    with (
        mock.patch("biotope.utils.find_biotope_root", return_value=git_repo),
        mock.patch(
            "biotope.commands.status._get_git_status", return_value={"staged": [], "modified": [], "untracked": []}
        ),
    ):
        with runner.isolated_filesystem():
            os.chdir(git_repo)
            result = runner.invoke(status, ["--detailed"])
    assert result.exit_code == 0
    assert "Validation Issues" not in result.output
