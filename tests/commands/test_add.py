"""Tests for the add command."""

import json
import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.add import (
    _add_file,
    add
)
from biotope.utils import is_git_repo, find_biotope_root, calculate_file_checksum, is_file_tracked, stage_git_changes


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
def biotope_project(tmp_path):
    """Create a mock biotope project structure."""
    # Create .biotope directory
    biotope_dir = tmp_path / ".biotope"
    biotope_dir.mkdir()
    
    # Create datasets directory
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir()
    
    # Create a sample metadata file
    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "existing_file",
        "description": "Dataset for existing_file.txt",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_12345678",
                "name": "existing_file.txt",
                "contentUrl": "existing_file.txt",
                "sha256": "1234567890abcdef",
                "contentSize": 100,
                "dateCreated": "2023-01-01T00:00:00Z"
            }
        ]
    }
    
    metadata_file = datasets_dir / "existing_file.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f)
    
    return tmp_path


@pytest.fixture
def git_repo(biotope_project):
    """Create a mock Git repository."""
    # Mock git commands
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        yield biotope_project


def test_calculate_file_checksum(sample_file):
    """Test checksum calculation."""
    import hashlib
    
    expected_hash = hashlib.sha256(sample_file.read_bytes()).hexdigest()
    assert calculate_file_checksum(sample_file) == expected_hash


def test_find_biotope_root(biotope_project):
    """Test finding biotope root directory."""
    # Test from biotope project root
    with mock.patch("pathlib.Path.cwd", return_value=biotope_project):
        result = find_biotope_root()
        assert result == biotope_project
    
    # Test from subdirectory
    subdir = biotope_project / "data" / "raw"
    subdir.mkdir(parents=True)
    
    with mock.patch("pathlib.Path.cwd", return_value=subdir):
        result = find_biotope_root()
        assert result == biotope_project
    
    # Test from outside biotope project
    outside_dir = biotope_project.parent / "outside"
    outside_dir.mkdir(exist_ok=True)
    
    with mock.patch("pathlib.Path.cwd", return_value=outside_dir):
        result = find_biotope_root()
        assert result is None


def test_is_git_repo(git_repo):
    """Test Git repository detection."""
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        assert is_git_repo(git_repo) is True
        
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        assert is_git_repo(git_repo) is False


def test_stage_git_changes(git_repo):
    """Test staging Git changes."""
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        stage_git_changes(git_repo)
        mock_run.assert_called_once_with(
            ["git", "add", ".biotope/"],
            cwd=git_repo,
            check=True
        )


def test_stage_git_changes_failure(git_repo):
    """Test staging Git changes when it fails."""
    with mock.patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        # Should not raise an exception
        stage_git_changes(git_repo)


def test_is_file_tracked_absolute_path(git_repo, sample_file):
    """Test checking if file is tracked with absolute path."""
    # Copy sample file to git_repo
    target_file = git_repo / sample_file.name
    target_file.write_text(sample_file.read_text())
    
    # Should not be tracked initially
    assert not is_file_tracked(target_file, git_repo)
    
    # Add the file
    _add_file(target_file, git_repo, git_repo / ".biotope" / "datasets", False)
    
    # Should be tracked now
    assert is_file_tracked(target_file, git_repo)


def test_is_file_tracked_relative_path(git_repo, sample_file):
    """Test checking if file is tracked with relative path."""
    # Create a subdirectory structure
    data_dir = git_repo / "data" / "raw"
    data_dir.mkdir(parents=True)
    
    # Create file in subdirectory
    target_file = data_dir / "experiment.csv"
    target_file.write_text("gene,expression\nBRCA1,12.5")
    
    # Change to git_repo directory to test relative path
    original_cwd = Path.cwd()
    try:
        # Change to git_repo directory
        import os
        os.chdir(git_repo)
        
        # Test with relative path
        relative_path = Path("data/raw/experiment.csv")
        assert not is_file_tracked(relative_path, git_repo)
        
        # Add the file
        _add_file(relative_path, git_repo, git_repo / ".biotope" / "datasets", False)
        
        # Should be tracked now
        assert is_file_tracked(relative_path, git_repo)
        
    finally:
        # Restore original directory
        os.chdir(original_cwd)


def test_add_file_absolute_path(git_repo, sample_file):
    """Test adding file with absolute path."""
    # Copy sample file to git_repo
    target_file = git_repo / sample_file.name
    target_file.write_text(sample_file.read_text())
    
    datasets_dir = git_repo / ".biotope" / "datasets"
    
    # Add the file
    result = _add_file(target_file, git_repo, datasets_dir, False)
    assert result is True
    
    # Check that metadata file was created with directory structure
    relative_path = target_file.relative_to(git_repo)
    metadata_file = datasets_dir / relative_path.with_suffix('.jsonld')
    assert metadata_file.exists()
    
    # Check metadata content
    with open(metadata_file) as f:
        metadata = json.load(f)
    
    assert metadata["name"] == target_file.stem
    assert metadata["distribution"][0]["name"] == target_file.name
    assert metadata["distribution"][0]["contentUrl"] == str(target_file.relative_to(git_repo))
    assert "sha256" in metadata["distribution"][0]


def test_add_file_relative_path(git_repo):
    """Test adding file with relative path."""
    # Create a subdirectory structure
    data_dir = git_repo / "data" / "raw"
    data_dir.mkdir(parents=True)
    
    # Create file in subdirectory
    target_file = data_dir / "experiment.csv"
    target_file.write_text("gene,expression\nBRCA1,12.5")
    
    datasets_dir = git_repo / ".biotope" / "datasets"
    
    # Change to git_repo directory to test relative path
    original_cwd = Path.cwd()
    try:
        # Change to git_repo directory
        import os
        os.chdir(git_repo)
        
        # Test with relative path
        relative_path = Path("data/raw/experiment.csv")
        
        # Add the file
        result = _add_file(relative_path, git_repo, datasets_dir, False)
        assert result is True
        
        # Check that metadata file was created with directory structure
        metadata_file = datasets_dir / relative_path.with_suffix('.jsonld')
        assert metadata_file.exists()
        
        # Check metadata content
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        assert metadata["name"] == relative_path.stem
        assert metadata["distribution"][0]["name"] == relative_path.name
        assert metadata["distribution"][0]["contentUrl"] == str(relative_path)
        assert "sha256" in metadata["distribution"][0]
        
    finally:
        # Restore original directory
        os.chdir(original_cwd)


def test_add_file_already_tracked(git_repo, sample_file):
    """Test adding file that is already tracked."""
    # Copy sample file to git_repo
    target_file = git_repo / sample_file.name
    target_file.write_text(sample_file.read_text())
    
    datasets_dir = git_repo / ".biotope" / "datasets"
    
    # Add the file first time
    result1 = _add_file(target_file, git_repo, datasets_dir, False)
    assert result1 is True
    
    # Try to add again without force
    result2 = _add_file(target_file, git_repo, datasets_dir, False)
    assert result2 is False
    
    # Try to add again with force
    result3 = _add_file(target_file, git_repo, datasets_dir, True)
    assert result3 is True


def test_add_file_relative_path_already_tracked(git_repo):
    """Test adding file with relative path that is already tracked."""
    # Create a subdirectory structure
    data_dir = git_repo / "data" / "raw"
    data_dir.mkdir(parents=True)
    
    # Create file in subdirectory
    target_file = data_dir / "experiment.csv"
    target_file.write_text("gene,expression\nBRCA1,12.5")
    
    datasets_dir = git_repo / ".biotope" / "datasets"
    
    # Change to git_repo directory to test relative path
    original_cwd = Path.cwd()
    try:
        # Change to git_repo directory
        import os
        os.chdir(git_repo)
        
        # Test with relative path
        relative_path = Path("data/raw/experiment.csv")
        
        # Add the file first time
        result1 = _add_file(relative_path, git_repo, datasets_dir, False)
        assert result1 is True
        
        # Try to add again without force
        result2 = _add_file(relative_path, git_repo, datasets_dir, False)
        assert result2 is False
        
        # Try to add again with force
        result3 = _add_file(relative_path, git_repo, datasets_dir, True)
        assert result3 is True
        
    finally:
        # Restore original directory
        os.chdir(original_cwd)


@mock.patch("biotope.utils.find_biotope_root")
@mock.patch("biotope.utils.is_git_repo")
@mock.patch("biotope.commands.add._add_file")
@mock.patch("biotope.commands.add.stage_git_changes")
def test_add_command_absolute_path(
    mock_stage, mock_add_file, mock_is_git, mock_find_root, runner, git_repo, sample_file
):
    """Test add command with absolute path."""
    # Setup mocks
    mock_find_root.return_value = git_repo
    mock_is_git.return_value = True
    mock_add_file.return_value = True
    
    # Copy sample file to git_repo
    target_file = git_repo / sample_file.name
    target_file.write_text(sample_file.read_text())
    
    # Run command
    with runner.isolated_filesystem():
        os.chdir(git_repo)
        result = runner.invoke(add, [str(target_file)])
    
    assert result.exit_code == 0
    mock_add_file.assert_called_once()
    mock_stage.assert_called_once_with(git_repo)


@mock.patch("biotope.utils.find_biotope_root")
@mock.patch("biotope.utils.is_git_repo")
@mock.patch("biotope.commands.add._add_file")
@mock.patch("biotope.commands.add.stage_git_changes")
def test_add_command_relative_path(
    mock_stage, mock_add_file, mock_is_git, mock_find_root, runner, git_repo
):
    """Test add command with relative path."""
    # Setup mocks
    mock_find_root.return_value = git_repo
    mock_is_git.return_value = True
    mock_add_file.return_value = True
    
    # Create a subdirectory structure
    data_dir = git_repo / "data" / "raw"
    data_dir.mkdir(parents=True)
    
    # Create file in subdirectory
    target_file = data_dir / "experiment.csv"
    target_file.write_text("gene,expression\nBRCA1,12.5")
    
    # Change to git_repo directory to test relative path
    original_cwd = Path.cwd()
    try:
        # Change to git_repo directory
        import os
        os.chdir(git_repo)
        
        # Run command with relative path
        result = runner.invoke(add, ["data/raw/experiment.csv"])
        
        assert result.exit_code == 0
        mock_add_file.assert_called_once()
        mock_stage.assert_called_once_with(git_repo)
        
    finally:
        # Restore original directory
        os.chdir(original_cwd)


@mock.patch("biotope.utils.find_biotope_root")
def test_add_command_no_biotope_project(mock_find_root, runner, tmp_path):
    """Test add command when not in a biotope project."""
    mock_find_root.return_value = None
    
    # Create a test file that exists
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    result = runner.invoke(add, [str(test_file)])
    
    assert result.exit_code != 0
    assert "Not in a biotope project" in result.output


@mock.patch("biotope.utils.find_biotope_root")
@mock.patch("biotope.utils.is_git_repo")
def test_add_command_no_git_repo(mock_is_git, mock_find_root, runner, biotope_project):
    """Test add command when not in a Git repository."""
    mock_find_root.return_value = biotope_project
    mock_is_git.return_value = False

    # Create a test file that exists
    test_file = biotope_project / "test.txt"
    test_file.write_text("test content")
    
    # Ensure .biotope directory exists so the CLI can find the project
    (biotope_project / ".biotope").mkdir(exist_ok=True)

    result = None
    with runner.isolated_filesystem():
        os.chdir(biotope_project)
        result = runner.invoke(add, [str(test_file)])
    assert result.exit_code != 0
    assert "Not in a Git repository" in result.output


def test_add_command_no_paths(runner):
    """Test add command with no paths specified."""
    result = runner.invoke(add, [])
    
    assert result.exit_code != 0
    assert "No paths specified" in result.output


@mock.patch("biotope.utils.find_biotope_root")
@mock.patch("biotope.utils.is_git_repo")
@mock.patch("biotope.commands.add._add_file")
@mock.patch("biotope.commands.add.stage_git_changes")
def test_add_command_recursive(
    mock_stage, mock_add_file, mock_is_git, mock_find_root, runner, git_repo
):
    """Test add command with recursive flag."""
    # Setup mocks
    mock_find_root.return_value = git_repo
    mock_is_git.return_value = True
    mock_add_file.return_value = True
    
    # Create a directory structure with files
    data_dir = git_repo / "data"
    data_dir.mkdir()
    
    file1 = data_dir / "file1.txt"
    file1.write_text("content1")
    
    subdir = data_dir / "subdir"
    subdir.mkdir()
    
    file2 = subdir / "file2.txt"
    file2.write_text("content2")
    
    # Run command with recursive flag
    with runner.isolated_filesystem():
        os.chdir(git_repo)
        result = runner.invoke(add, ["--recursive", str(data_dir)])
    
    assert result.exit_code == 0
    # Should be called twice (once for each file)
    assert mock_add_file.call_count == 2
    mock_stage.assert_called_once_with(git_repo)


@mock.patch("biotope.utils.find_biotope_root")
@mock.patch("biotope.utils.is_git_repo")
@mock.patch("biotope.commands.add._add_file")
@mock.patch("biotope.commands.add.stage_git_changes")
def test_add_command_directory_without_recursive(
    mock_stage, mock_add_file, mock_is_git, mock_find_root, runner, git_repo
):
    """Test add command with directory but no recursive flag."""
    # Setup mocks
    mock_find_root.return_value = git_repo
    mock_is_git.return_value = True
    
    # Create a directory
    data_dir = git_repo / "data"
    data_dir.mkdir()
    
    # Run command without recursive flag
    with runner.isolated_filesystem():
        os.chdir(git_repo)
        result = runner.invoke(add, [str(data_dir)])
    
    assert result.exit_code == 0
    # Should not call _add_file for directories
    mock_add_file.assert_not_called()
    # Should not stage changes since no files were added
    mock_stage.assert_not_called()
    assert "Skipping directory" in result.output


@mock.patch("biotope.utils.find_biotope_root")
@mock.patch("biotope.utils.is_git_repo")
@mock.patch("biotope.commands.add._add_file")
@mock.patch("biotope.commands.add.stage_git_changes")
def test_add_command_mixed_success_and_failure(
    mock_stage, mock_add_file, mock_is_git, mock_find_root, runner, git_repo, sample_file
):
    """Test add command with some files succeeding and some failing."""
    # Setup mocks
    mock_find_root.return_value = git_repo
    mock_is_git.return_value = True
    
    # Copy sample file to git_repo
    target_file = git_repo / sample_file.name
    target_file.write_text(sample_file.read_text())
    
    # Create another file
    another_file = git_repo / "another.txt"
    another_file.write_text("another content")
    
    # Mock _add_file to return different results
    def mock_add_file_side_effect(file_path, biotope_root, datasets_dir, force):
        return file_path.name == sample_file.name
    
    mock_add_file.side_effect = mock_add_file_side_effect
    
    # Run command
    with runner.isolated_filesystem():
        os.chdir(git_repo)
        result = runner.invoke(add, [str(target_file), str(another_file)])
    
    assert result.exit_code == 0
    assert mock_add_file.call_count == 2
    # Should stage changes since at least one file was added
    mock_stage.assert_called_once_with(git_repo)
    assert "Added 1 file(s)" in result.output
    assert "Skipped 1 file(s)" in result.output 