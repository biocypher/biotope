"""Tests for annotate interactive --incomplete."""

from __future__ import annotations

import json
from unittest import mock

import pytest
import yaml
from click.testing import CliRunner

from biotope.commands.annotate import interactive
from tests.conftest import ANNOTATION_VALIDATION_CONFIG


@pytest.fixture
def runner():
    return CliRunner()


def _prompt_side_effect(*args, **kwargs):
    prompt_text = args[0] if args else ""
    if "Dataset name" in prompt_text:
        return "test_dataset"
    if "description" in prompt_text.lower():
        return "A test dataset for validation"
    if "Contact person" in prompt_text:
        return "John Doe"
    if "Creation date" in prompt_text:
        return "2024-01-01"
    return "test-value"


@mock.patch("biotope.commands.annotate.find_biotope_root")
@mock.patch("biotope.commands.annotate.get_staged_files")
def test_interactive_incomplete_finds_incomplete_files(mock_get_staged_files, mock_find_root, runner, git_repo):
    mock_find_root.return_value = git_repo
    (git_repo / ".biotope" / "config.yaml").write_text(yaml.dump(ANNOTATION_VALIDATION_CONFIG))

    metadata_file = git_repo / ".biotope" / "datasets" / "test_dataset.jsonld"
    metadata_file.write_text(
        json.dumps(
            {
                "@context": {"@vocab": "https://schema.org/"},
                "@type": "Dataset",
                "name": "test_dataset",
                "description": "Dataset for test.csv",
                "distribution": [
                    {
                        "@type": "cr:FileObject",
                        "@id": "file_12345678",
                        "name": "test.csv",
                        "contentUrl": "data/test.csv",
                        "sha256": "1234567890abcdef",
                        "contentSize": 100,
                    }
                ],
            }
        )
    )

    with (
        mock.patch("click.prompt", side_effect=_prompt_side_effect),
        mock.patch("click.confirm", return_value=False),
        mock.patch("rich.prompt.Prompt.ask", return_value="test-value"),
        mock.patch("rich.prompt.Confirm.ask", return_value=False),
    ):
        result = runner.invoke(interactive, ["--incomplete"])

    assert result.exit_code == 0
    assert "Found 1 file(s) with incomplete annotation" in result.output
    updated = json.loads(metadata_file.read_text())
    assert updated["creator"]["name"] == "John Doe"
    assert updated["dateCreated"] == "2024-01-01"


@mock.patch("biotope.commands.annotate.find_biotope_root")
def test_interactive_incomplete_no_incomplete_files(mock_find_root, runner, git_repo):
    mock_find_root.return_value = git_repo
    (git_repo / ".biotope" / "config.yaml").write_text(yaml.dump(ANNOTATION_VALIDATION_CONFIG))
    (git_repo / ".biotope" / "datasets" / "complete_dataset.jsonld").write_text(
        json.dumps(
            {
                "@context": {"@vocab": "https://schema.org/"},
                "@type": "Dataset",
                "name": "complete_dataset",
                "description": "A complete dataset with all required fields",
                "creator": {"name": "John Doe", "email": "john@example.com"},
                "dateCreated": "2024-01-01",
                "distribution": [
                    {
                        "@type": "cr:FileObject",
                        "@id": "file_12345678",
                        "name": "complete.csv",
                        "contentUrl": "data/complete.csv",
                        "sha256": "1234567890abcdef",
                        "contentSize": 100,
                    }
                ],
            }
        )
    )
    result = runner.invoke(interactive, ["--incomplete"])
    assert result.exit_code == 0
    assert "All tracked files are properly annotated!" in result.output


@mock.patch("biotope.commands.annotate.find_biotope_root")
def test_interactive_incomplete_no_tracked_files(mock_find_root, runner, git_repo):
    mock_find_root.return_value = git_repo
    config = {"annotation_validation": {"enabled": True, "minimum_required_fields": ["name", "description"]}}
    (git_repo / ".biotope" / "config.yaml").write_text(yaml.dump(config))
    result = runner.invoke(interactive, ["--incomplete"])
    assert result.exit_code != 0
    assert "No tracked files found" in result.output


@mock.patch("biotope.commands.annotate.find_biotope_root")
def test_interactive_incomplete_no_biotope_project(mock_find_root, runner):
    mock_find_root.return_value = None
    result = runner.invoke(interactive, ["--incomplete"])
    assert result.exit_code != 0
    assert "Not in a biotope project" in result.output
