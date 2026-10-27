"""Tests for the annotate command surface."""

from __future__ import annotations

import subprocess
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.annotate import validate


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_metadata_file(tmp_path):
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text("")
    return metadata_path


@mock.patch("subprocess.run")
def test_validate_command_success(mock_run, runner, sample_metadata_file):
    mock_process = mock.Mock()
    mock_process.stdout = "Done"
    mock_process.stderr = ""
    mock_run.return_value = mock_process

    result = runner.invoke(validate, ["--jsonld", str(sample_metadata_file)])

    assert result.exit_code == 0
    assert "Validation successful!" in result.output


@mock.patch("subprocess.run")
def test_validate_command_failure(mock_run, runner, sample_metadata_file):
    mock_run.side_effect = subprocess.CalledProcessError(
        1,
        ["mlcroissant", "validate"],
        stderr="Invalid schema: missing required field",
    )

    result = runner.invoke(validate, ["--jsonld", str(sample_metadata_file)])
    assert result.exit_code == 1
    assert "Validation failed" in result.output
