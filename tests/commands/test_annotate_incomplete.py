"""Tests for the annotate interactive --incomplete command."""

import json
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.annotate import interactive


def debug_prompt(*args, **kwargs):
    print(f"click.prompt called with args: {args}, kwargs: {kwargs}")
    # Return appropriate values based on the prompt
    prompt_text = args[0] if args else ""
    if "Dataset name" in prompt_text:
        return "test_dataset"
    elif "description" in prompt_text.lower():
        return "A test dataset for validation"
    elif "Data source" in prompt_text:
        return "https://example.com/test"
    elif "Project name" in prompt_text:
        return "Test Project"
    elif "Contact person" in prompt_text:
        return "John Doe"
    elif "Creation date" in prompt_text:
        return "2024-01-01"
    elif "File format" in prompt_text:
        return "text/csv"
    elif "Legal obligations" in prompt_text:
        return "None"
    elif "Collaboration partner" in prompt_text:
        return "Test Institute"
    elif "Publication date" in prompt_text:
        return "2024-01-01"
    elif "Dataset version" in prompt_text:
        return "1.0"
    elif "License URL" in prompt_text:
        return "https://creativecommons.org/licenses/by/4.0/"
    elif "Citation text" in prompt_text:
        return "Please cite this dataset as: test_dataset (2024)"
    else:
        return "test-value"


def debug_rich_prompt(*args, **kwargs):
    print(f"rich.prompt.Prompt.ask called with args: {args}, kwargs: {kwargs}")
    return "test-value"


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

    # Create config directory

    # Create datasets directory
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir()

    return tmp_path


@pytest.fixture
def git_repo(biotope_project):
    """Create a mock Git repository."""
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        yield biotope_project


@mock.patch("biotope.commands.annotate.find_biotope_root")
@mock.patch("biotope.commands.annotate.get_staged_files")
def test_interactive_incomplete_finds_incomplete_files(mock_get_staged_files, mock_find_root, runner, git_repo):
    """Test that interactive --incomplete finds files with incomplete metadata."""
    # Setup mocks
    mock_find_root.return_value = git_repo

    # Create biotope config with default validation
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": ["name", "description", "creator", "dateCreated", "distribution"],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1},
            },
        }
    }

    config_file = git_repo / ".biotope" / "config.yaml"
    import yaml

    with open(config_file, "w") as f:
        yaml.dump(config, f)

    # Create incomplete metadata file (like biotope add would create)
    incomplete_metadata = {
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

    metadata_file = git_repo / ".biotope" / "datasets" / "test_dataset.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(incomplete_metadata, f)

        # Mock the interactive prompts to return valid values
        with (
            mock.patch("click.prompt") as mock_prompt,
            mock.patch("click.confirm") as mock_confirm,
            mock.patch("rich.prompt.Prompt.ask") as mock_rich_prompt,
            mock.patch("rich.prompt.Confirm.ask") as mock_rich_confirm_ask,
        ):
            # Mock all the interactive prompts
            mock_prompt.side_effect = debug_prompt
            mock_rich_prompt.side_effect = debug_rich_prompt

            # Mock confirm prompts to return False (no) for most prompts to avoid complex flows
            def mock_confirm_side_effect(*args, **kwargs):
                print(f"click.confirm called with args: {args}, kwargs: {kwargs}")
                return False

            def mock_rich_confirm_side_effect(*args, **kwargs):
                print(f"rich.prompt.Confirm.ask called with args: {args}, kwargs: {kwargs}")
                return False

            mock_confirm.side_effect = mock_confirm_side_effect
            mock_rich_confirm_ask.side_effect = mock_rich_confirm_side_effect

            # Run the command
            result = runner.invoke(interactive, ["--incomplete"])

            # Debug output
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            print(f"Exception: {result.exception}")

            # Check that it ran successfully
            assert result.exit_code == 0

        # Check that it found the incomplete file
        assert "Found 1 file(s) with incomplete annotation" in result.output
        assert "test_dataset" in result.output

        # Check that it called the interactive prompts
        assert mock_prompt.call_count > 0

        # Check that the metadata file was updated with complete information
        with open(metadata_file) as f:
            updated_metadata = json.load(f)

        # Should now have all required fields
        assert "creator" in updated_metadata
        assert "dateCreated" in updated_metadata
        assert updated_metadata["creator"]["name"] == "John Doe"
        assert updated_metadata["dateCreated"] == "2024-01-01"


@mock.patch("biotope.commands.annotate.find_biotope_root")
def test_interactive_incomplete_no_incomplete_files(mock_find_root, runner, git_repo):
    """Test that interactive --incomplete shows success when all files are complete."""
    # Setup mocks
    mock_find_root.return_value = git_repo

    # Create biotope config with default validation
    config = {
        "annotation_validation": {
            "enabled": True,
            "minimum_required_fields": ["name", "description", "creator", "dateCreated", "distribution"],
            "field_validation": {
                "name": {"type": "string", "min_length": 1},
                "description": {"type": "string", "min_length": 10},
                "creator": {"type": "object", "required_keys": ["name"]},
                "dateCreated": {"type": "string", "format": "date"},
                "distribution": {"type": "array", "min_length": 1},
            },
        }
    }

    config_file = git_repo / ".biotope" / "config.yaml"
    import yaml

    with open(config_file, "w") as f:
        yaml.dump(config, f)

    # Create complete metadata file
    complete_metadata = {
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

    metadata_file = git_repo / ".biotope" / "datasets" / "complete_dataset.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(complete_metadata, f)

    # Run the command
    result = runner.invoke(interactive, ["--incomplete"])

    # Check that it ran successfully
    assert result.exit_code == 0

    # Check that it shows all files are complete
    assert "All tracked files are properly annotated!" in result.output


@mock.patch("biotope.commands.annotate.find_biotope_root")
def test_interactive_incomplete_no_tracked_files(mock_find_root, runner, git_repo):
    """Test that interactive --incomplete handles case with no tracked files."""
    # Setup mocks
    mock_find_root.return_value = git_repo

    # Create biotope config
    config = {"annotation_validation": {"enabled": True, "minimum_required_fields": ["name", "description"]}}

    config_file = git_repo / ".biotope" / "config.yaml"
    import yaml

    with open(config_file, "w") as f:
        yaml.dump(config, f)

    # Run the command (no metadata files exist)
    result = runner.invoke(interactive, ["--incomplete"])

    # Check that it shows appropriate message
    assert result.exit_code != 0
    assert "No tracked files found" in result.output


@mock.patch("biotope.commands.annotate.find_biotope_root")
def test_interactive_incomplete_no_biotope_project(mock_find_root, runner):
    """Test that interactive --incomplete handles case when not in biotope project."""
    # Setup mocks
    mock_find_root.return_value = None

    # Run the command
    result = runner.invoke(interactive, ["--incomplete"])

    # Check that it shows appropriate message
    assert result.exit_code != 0
    assert "Not in a biotope project" in result.output
