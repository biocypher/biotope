"""Tests for the get command."""

import subprocess
from unittest import mock

import pytest
import requests
from click.testing import CliRunner

from biotope.commands.get import (
    download_file,
    _call_biotope_add,
)
from biotope.utils import is_git_repo, find_biotope_root


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_file(tmp_path):
    """Create a sample file for testing."""
    file_path = tmp_path / "test.txt"
    content = "This is a test file content"
    file_path.write_text(content)
    return file_path


@pytest.fixture
def mock_response():
    """Create a mock response for requests.get."""
    mock_resp = mock.Mock()
    mock_resp.headers = {"content-length": "100"}
    mock_resp.iter_content.return_value = [b"test content"]
    mock_resp.raise_for_status.return_value = None
    return mock_resp


@pytest.fixture
def biotope_project(tmp_path):
    """Create a temporary biotope project for testing."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create .biotope directory structure
    biotope_dir = project_dir / ".biotope"
    biotope_dir.mkdir()
    (biotope_dir / "datasets").mkdir()
    (biotope_dir / "config").mkdir()

    # Create basic config
    config_file = biotope_dir / "config" / "biotope.yaml"
    config_file.write_text("project_name: test_project\n")

    # Initialize git repository
    subprocess.run(["git", "init"], cwd=project_dir, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=project_dir, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=project_dir, check=True
    )

    return project_dir


@mock.patch("requests.get")
def test_download_file_success(mock_get, tmp_path, mock_response):
    """Test successful file download."""
    mock_get.return_value = mock_response
    url = "https://example.com/test.txt"
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()

    result = download_file(url, output_dir)
    assert result is not None
    assert result.exists()
    assert result.name == "test.txt"
    assert result.parent == output_dir

    mock_get.assert_called_once_with(url, stream=True, timeout=30)


@mock.patch("requests.get")
def test_download_file_with_content_disposition(mock_get, tmp_path):
    """Test file download with Content-Disposition header."""
    mock_resp = mock.Mock()
    mock_resp.headers = {
        "content-length": "100",
        "Content-Disposition": 'attachment; filename="custom_name.csv"',
    }
    mock_resp.iter_content.return_value = [b"test content"]
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    url = "https://example.com/test.txt"
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()

    result = download_file(url, output_dir)
    assert result is not None
    assert result.name == "custom_name.csv"


@mock.patch("requests.get")
def test_download_file_failure(mock_get, tmp_path):
    """Test file download failure."""
    mock_get.side_effect = requests.RequestException("Download failed")
    url = "https://example.com/test.txt"
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()

    result = download_file(url, output_dir)
    assert result is None


def test_find_biotope_root(biotope_project):
    """Test finding biotope project root."""
    # Test from project root
    with mock.patch("pathlib.Path.cwd", return_value=biotope_project):
        result = find_biotope_root()
        assert result == biotope_project

    # Test from subdirectory
    subdir = biotope_project / "subdir"
    subdir.mkdir()

    with mock.patch("pathlib.Path.cwd", return_value=subdir):
        result = find_biotope_root()
        assert result == biotope_project


def test_find_biotope_root_not_found(tmp_path):
    """Test finding biotope project root when not in a project."""
    with mock.patch("pathlib.Path.cwd", return_value=tmp_path):
        result = find_biotope_root()
        assert result is None


def test_is_git_repo(biotope_project):
    """Test Git repository detection."""
    assert is_git_repo(biotope_project) is True


def test_is_git_repo_not_git(tmp_path):
    """Test Git repository detection when not a Git repo."""
    assert is_git_repo(tmp_path) is False


@mock.patch("biotope.commands.get._add_file")
@mock.patch("biotope.commands.get.stage_git_changes")
def test_call_biotope_add_success(mock_stage, mock_add, biotope_project):
    """Test successful biotope add call."""
    sample_file = biotope_project / "test_data.txt"
    sample_file.write_text("This is test content")

    mock_add.return_value = True

    result = _call_biotope_add(sample_file, biotope_project)

    assert result is True
    mock_add.assert_called_once_with(
        sample_file,
        biotope_project,
        biotope_project / ".biotope" / "datasets",
        force=False,
    )
    mock_stage.assert_called_once_with(biotope_project)


@mock.patch("biotope.commands.get._add_file")
@mock.patch("biotope.commands.get.stage_git_changes")
def test_call_biotope_add_failure(mock_stage, mock_add, biotope_project):
    """Test biotope add call when add fails."""
    sample_file = biotope_project / "test_data.txt"
    sample_file.write_text("This is test content")

    mock_add.return_value = False

    result = _call_biotope_add(sample_file, biotope_project)

    assert result is False
    mock_add.assert_called_once()
    mock_stage.assert_not_called()


@mock.patch("biotope.commands.get._add_file")
def test_call_biotope_add_exception(mock_add, biotope_project):
    """Test biotope add call when exception occurs."""
    sample_file = biotope_project / "test_data.txt"
    sample_file.write_text("This is test content")

    mock_add.side_effect = Exception("Add failed")

    result = _call_biotope_add(sample_file, biotope_project)

    assert result is False


@mock.patch("biotope.commands.get.download_file")
@mock.patch("biotope.commands.get._call_biotope_add")
def test_get_command_success(mock_add, mock_download, runner, biotope_project):
    """Test successful get command execution."""
    from biotope.commands.get import get

    # Setup mocks
    downloaded_file = biotope_project / "downloads" / "test.txt"
    downloaded_file.parent.mkdir(parents=True, exist_ok=True)
    downloaded_file.write_text("test content")
    mock_download.return_value = downloaded_file
    mock_add.return_value = True

    with mock.patch(
        "biotope.commands.get.find_biotope_root", return_value=biotope_project
    ):
        with mock.patch("biotope.commands.get.is_git_repo", return_value=True):
            result = runner.invoke(get, ["https://example.com/test.txt"])

    assert result.exit_code == 0
    assert "📥 Downloading file from:" in result.output
    assert "✅ Downloaded:" in result.output
    assert "📁 Adding file to biotope project..." in result.output
    assert "✅ File added to biotope project" in result.output
    assert "Next steps:" in result.output

    mock_download.assert_called_once()
    mock_add.assert_called_once()


@mock.patch("biotope.commands.get.download_file")
def test_get_command_download_failure(mock_download, runner, biotope_project):
    """Test get command when download fails."""
    from biotope.commands.get import get

    mock_download.return_value = None

    with mock.patch(
        "biotope.commands.get.find_biotope_root", return_value=biotope_project
    ):
        with mock.patch("biotope.commands.get.is_git_repo", return_value=True):
            result = runner.invoke(get, ["https://example.com/test.txt"])

    assert result.exit_code == 1  # Should abort on download failure
    assert "❌ Failed to download file" in result.output


@mock.patch("biotope.commands.get.download_file")
@mock.patch("biotope.commands.get._call_biotope_add")
def test_get_command_add_failure(mock_add, mock_download, runner, biotope_project):
    """Test get command when add fails."""
    from biotope.commands.get import get

    downloaded_file = biotope_project / "downloads" / "test.txt"
    downloaded_file.parent.mkdir(parents=True, exist_ok=True)
    downloaded_file.write_text("test content")
    mock_download.return_value = downloaded_file
    mock_add.return_value = False

    with mock.patch(
        "biotope.commands.get.find_biotope_root", return_value=biotope_project
    ):
        with mock.patch("biotope.commands.get.is_git_repo", return_value=True):
            result = runner.invoke(get, ["https://example.com/test.txt"])

    assert result.exit_code == 0
    assert "⚠️  File downloaded but not added to biotope project" in result.output
    assert "You can manually add it with:" in result.output


@mock.patch("biotope.commands.get.download_file")
def test_get_command_no_add_flag(mock_download, runner, biotope_project):
    """Test get command with --no-add flag."""
    from biotope.commands.get import get

    downloaded_file = biotope_project / "downloads" / "test.txt"
    downloaded_file.parent.mkdir(parents=True, exist_ok=True)
    downloaded_file.write_text("test content")
    mock_download.return_value = downloaded_file

    with mock.patch(
        "biotope.commands.get.find_biotope_root", return_value=biotope_project
    ):
        with mock.patch("biotope.commands.get.is_git_repo", return_value=True):
            result = runner.invoke(get, ["https://example.com/test.txt", "--no-add"])

    assert result.exit_code == 0
    assert "✅ Downloaded:" in result.output
    assert "📁 Adding file to biotope project..." not in result.output
    assert "File downloaded. To add to biotope project:" in result.output


def test_get_command_not_in_biotope_project(runner):
    """Test get command when not in a biotope project."""
    from biotope.commands.get import get

    with mock.patch("biotope.commands.get.find_biotope_root", return_value=None):
        result = runner.invoke(get, ["https://example.com/test.txt"])

    assert result.exit_code == 1
    assert "❌ Not in a biotope project" in result.output


def test_get_command_not_in_git_repo(runner, biotope_project):
    """Test get command when not in a Git repository."""
    from biotope.commands.get import get

    with mock.patch(
        "biotope.commands.get.find_biotope_root", return_value=biotope_project
    ):
        with mock.patch("biotope.commands.get.is_git_repo", return_value=False):
            result = runner.invoke(get, ["https://example.com/test.txt"])

    assert result.exit_code == 1
    assert "❌ Not in a Git repository" in result.output


@mock.patch("biotope.commands.get.download_file")
@mock.patch("biotope.commands.get._call_biotope_add")
def test_get_command_custom_output_dir(
    mock_add, mock_download, runner, biotope_project
):
    """Test get command with custom output directory."""
    from biotope.commands.get import get

    custom_dir = biotope_project / "custom_downloads"
    downloaded_file = custom_dir / "test.txt"
    mock_download.return_value = downloaded_file
    mock_add.return_value = True

    with mock.patch(
        "biotope.commands.get.find_biotope_root", return_value=biotope_project
    ):
        with mock.patch("biotope.commands.get.is_git_repo", return_value=True):
            result = runner.invoke(
                get, ["https://example.com/test.txt", "--output-dir", str(custom_dir)]
            )

    assert result.exit_code == 0
    mock_download.assert_called_once()
    # Check that the output directory was passed correctly
    call_args = mock_download.call_args[0]
    assert call_args[1] == custom_dir
