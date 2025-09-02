"""Tests for the annotate interactive --staged command."""

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.annotate import interactive


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def biotope_project(tmp_path):
    """Create a mock biotope project structure."""
    # Create .biotope directory
    biotope_dir = tmp_path / ".biotope"
    biotope_dir.mkdir()
    
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    
    # Create datasets directory
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir()
    
    return tmp_path


@pytest.fixture
def git_repo(biotope_project):
    """Create a mock Git repository."""
    # Mock git commands
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        yield biotope_project


@mock.patch("biotope.commands.annotate.find_biotope_root")
@mock.patch("biotope.commands.annotate.get_staged_files")
def test_interactive_staged_runs_interactive_mode(
    mock_get_staged_files, mock_find_root, runner, git_repo
):
    """Test that interactive --staged actually runs interactive mode."""
    # Setup mocks
    mock_find_root.return_value = git_repo

    # Mock staged files
    mock_get_staged_files.return_value = [
        {
            "file_path": "data/test.csv",
            "sha256": "1234567890abcdef",
            "size": 100
        }
    ]

    # Create the actual data file that the staged file references
    data_file = git_repo / "data" / "test.csv"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text("gene,expression\nBRCA1,12.5")

    # Mock the interactive prompts to avoid hanging
    with mock.patch("click.prompt") as mock_prompt:
        mock_prompt.side_effect = [
            "test_dataset",  # dataset name
            "Test dataset description",  # description
            "https://example.com/data",  # data source
            "test_project",  # project name
            "test@example.com",  # contact
            "2024-01-01",  # creation date
            "text/csv",  # format
            "",  # legal obligations
            "",  # collaboration partner
            "2024-01-01",  # publication date
            "1.0",  # version
            "https://creativecommons.org/licenses/by/4.0/",  # license
            "Please cite this dataset",  # citation
        ]

        with mock.patch("rich.prompt.Confirm.ask") as mock_confirm:
            mock_confirm.return_value = False  # No access restrictions

            # Run the command
            result = runner.invoke(interactive, ["--staged"])

            # Debug output
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            print(f"Exception: {result.exception}")
            print(f"Prompt calls: {mock_prompt.call_count}")

            # Check that it ran successfully
            assert result.exit_code == 0

            # Check that it called the interactive prompts
            assert mock_prompt.call_count > 0

            # Check that it created a metadata file
            # The file should be named after the dataset name, not the original file name
            metadata_file = git_repo / ".biotope" / "datasets" / "test_dataset.jsonld"
            print(f"Metadata file exists: {metadata_file.exists()}")
            print(f"Datasets dir contents: {list((git_repo / '.biotope' / 'datasets').glob('*'))}")
            assert metadata_file.exists()

            # Check the metadata content
            with open(metadata_file) as f:
                metadata = json.load(f)

            assert metadata["name"] == "test_dataset"
            assert metadata["description"] == "Test dataset description"
            assert metadata["url"] == "https://example.com/data"


@mock.patch("biotope.commands.annotate.find_biotope_root")
@mock.patch("biotope.commands.annotate.get_staged_files")
def test_interactive_staged_no_staged_files(
    mock_get_staged_files, mock_find_root, runner, git_repo
):
    """Test that interactive --staged fails when no files are staged."""
    # Setup mocks
    mock_find_root.return_value = git_repo
    mock_get_staged_files.return_value = []
    
    # Run the command
    result = runner.invoke(interactive, ["--staged"])
    
    # Check that it failed with appropriate message
    assert result.exit_code != 0
    assert "No files staged" in result.output


@mock.patch("biotope.commands.annotate.find_biotope_root")
def test_interactive_staged_no_biotope_project(mock_find_root, runner):
    """Test that interactive --staged fails when not in a biotope project."""
    # Setup mocks
    mock_find_root.return_value = None
    
    # Run the command
    result = runner.invoke(interactive, ["--staged"])
    
    # Check that it failed with appropriate message
    assert result.exit_code != 0
    assert "Not in a biotope project" in result.output 