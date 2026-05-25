"""Tests for the improved status command workflow."""

from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.status import status


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


@mock.patch("biotope.commands.status.find_biotope_root")
@mock.patch("biotope.utils.is_git_repo")
@mock.patch("biotope.commands.status._get_git_status")
def test_status_suggests_biotope_commands_not_git(mock_get_status, mock_is_git, mock_find_root, runner, git_repo):
    """Test that status suggests biotope commands instead of Git commands."""
    # Setup mocks
    mock_find_root.return_value = git_repo
    mock_is_git.return_value = True

    # Mock Git status to show unstaged changes
    mock_get_status.return_value = {"staged": [], "modified": [("M", ".biotope/datasets/test.jsonld")], "untracked": []}

    # Run status command
    result = runner.invoke(status)

    assert result.exit_code == 0

    # Check that it suggests biotope commands, not Git commands
    assert "git add .biotope/" not in result.output
    assert "biotope add" in result.output
    assert "biotope annotate" in result.output
    assert "biotope commit" in result.output


@mock.patch("biotope.commands.status.find_biotope_root")
@mock.patch("biotope.utils.is_git_repo")
@mock.patch("biotope.commands.status._get_git_status")
def test_status_suggests_commit_when_staged(mock_get_status, mock_is_git, mock_find_root, runner, git_repo):
    """Test that status suggests commit when changes are staged."""
    # Setup mocks
    mock_find_root.return_value = git_repo
    mock_is_git.return_value = True

    # Mock Git status to show staged changes
    mock_get_status.return_value = {"staged": [("A", ".biotope/datasets/test.jsonld")], "modified": [], "untracked": []}

    # Run status command
    result = runner.invoke(status)

    assert result.exit_code == 0

    # Check that it suggests commit
    assert "biotope commit" in result.output
    # Should not suggest add or annotate when already staged
    assert "biotope add" not in result.output
    assert "biotope annotate" not in result.output
