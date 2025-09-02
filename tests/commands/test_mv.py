"""Tests for the mv command."""

import json
import os
import shutil
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner

from biotope.commands.mv import (
    mv,
    _find_metadata_files_for_file,
    _find_tracked_files_in_directory,
    _resolve_destination_path,
    _update_metadata_file_path,
    _validate_move_operation,
)


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
    
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    
    # Create datasets directory
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir()
    
    return tmp_path


@pytest.fixture
def biotope_project_with_file(tmp_path):
    """Create biotope project with tracked file."""
    # Create .biotope structure
    biotope_dir = tmp_path / ".biotope"
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    
    # Create test data file
    data_dir = tmp_path / "data" / "raw"
    data_dir.mkdir(parents=True)
    test_file = data_dir / "test.csv"
    test_file.write_text("gene,expression\nBRCA1,12.5")
    
    # Create metadata file with directory structure mirroring
    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "test",
        "description": "Dataset for test.csv",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_12345678",
                "name": "test.csv",
                "contentUrl": "data/raw/test.csv",
                "sha256": "abc123",
                "contentSize": 100,
                "dateCreated": "2023-01-01T00:00:00Z"
            }
        ]
    }
    
    # Create metadata file in directory structure that mirrors data file location
    metadata_dir = datasets_dir / "data" / "raw"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_file = metadata_dir / "test.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    
    return tmp_path


@pytest.fixture
def git_repo(biotope_project):
    """Create a mock Git repository."""
    # Mock git commands
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        yield biotope_project


def test_find_metadata_files_for_file(biotope_project_with_file):
    """Test finding metadata files that reference a data file."""
    test_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    metadata_files = _find_metadata_files_for_file(test_file, biotope_project_with_file)
    
    assert len(metadata_files) == 1
    assert metadata_files[0].name == "test.jsonld"


def test_find_metadata_files_for_file_no_matches(biotope_project_with_file):
    """Test finding metadata files when no matches exist."""
    nonexistent_file = biotope_project_with_file / "data" / "raw" / "nonexistent.csv"
    metadata_files = _find_metadata_files_for_file(nonexistent_file, biotope_project_with_file)
    
    assert len(metadata_files) == 0


def test_find_metadata_files_for_file_no_datasets_dir(biotope_project):
    """Test finding metadata files when datasets directory doesn't exist."""
    test_file = biotope_project / "test.csv"
    test_file.write_text("test content")
    
    metadata_files = _find_metadata_files_for_file(test_file, biotope_project)
    
    assert len(metadata_files) == 0


def test_update_metadata_file_path(biotope_project_with_file):
    """Test updating file path in metadata file."""
    metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "test.jsonld"
    
    # Create the destination directory and file for size calculation
    dest_dir = biotope_project_with_file / "data" / "processed"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / "test.csv"
    dest_file.write_text("gene,expression\nBRCA1,12.5")  # Same content as source
    
    # Update the path
    result = _update_metadata_file_path(
        metadata_file,
        "data/raw/test.csv",
        "data/processed/test.csv",
        "new_checksum_123",
        biotope_project_with_file
    )
    
    assert result is True
    
    # Verify the metadata was updated
    with open(metadata_file) as f:
        metadata = json.load(f)
    
    distribution = metadata["distribution"][0]
    assert distribution["contentUrl"] == "data/processed/test.csv"
    assert distribution["sha256"] == "new_checksum_123"
    assert "dateModified" in distribution


def test_update_metadata_file_path_no_match(biotope_project_with_file):
    """Test updating file path when no matching file object exists."""
    metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "test.jsonld"
    
    # Try to update a path that doesn't exist in metadata
    result = _update_metadata_file_path(
        metadata_file,
        "data/raw/nonexistent.csv",
        "data/processed/nonexistent.csv",
        "new_checksum_123",
        biotope_project_with_file
    )
    
    assert result is False


def test_update_metadata_file_path_invalid_json(biotope_project):
    """Test updating file path with invalid JSON."""
    metadata_file = biotope_project / ".biotope" / "datasets" / "data" / "raw" / "invalid.jsonld"
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.write_text("invalid json content")
    
    result = _update_metadata_file_path(
        metadata_file,
        "data/raw/test.csv",
        "data/processed/test.csv",
        "new_checksum_123",
        biotope_project
    )
    
    assert result is False


def test_validate_move_operation_outside_project(biotope_project):
    """Test validation when trying to move file outside project."""
    source = biotope_project / "test.csv"
    source.write_text("test content")
    destination = biotope_project.parent / "outside.csv"
    
    with pytest.raises(click.Abort):
        _validate_move_operation(source, destination, biotope_project, False)


def test_validate_move_operation_same_file(biotope_project):
    """Test validation when source and destination are the same."""
    source = biotope_project / "test.csv"
    source.write_text("test content")
    destination = source
    
    with pytest.raises(click.Abort):
        _validate_move_operation(source, destination, biotope_project, False)


def test_validate_move_operation_biotope_internal_file(biotope_project):
    """Test validation when trying to move biotope internal files."""
    source = biotope_project / ".biotope" / "datasets" / "data" / "raw" / "test.jsonld"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("metadata content")
    destination = biotope_project / "test.jsonld"
    
    with pytest.raises(click.Abort):
        _validate_move_operation(source, destination, biotope_project, False)


def test_validate_move_operation_destination_exists_no_force(biotope_project):
    """Test validation when destination exists and force is not used."""
    source = biotope_project / "source.csv"
    source.write_text("source content")
    destination = biotope_project / "destination.csv"
    destination.write_text("destination content")
    
    with pytest.raises(click.Abort):
        _validate_move_operation(source, destination, biotope_project, False)


def test_validate_move_operation_destination_exists_with_force(biotope_project):
    """Test validation when destination exists and force is used."""
    source = biotope_project / "source.csv"
    source.write_text("source content")
    destination = biotope_project / "destination.csv"
    destination.write_text("destination content")
    
    # Should not raise an exception
    _validate_move_operation(source, destination, biotope_project, True)


def test_validate_move_operation_valid(biotope_project):
    """Test validation with valid move operation."""
    source = biotope_project / "source.csv"
    source.write_text("source content")
    destination = biotope_project / "data" / "destination.csv"
    
    # Should not raise an exception
    _validate_move_operation(source, destination, biotope_project, False)


def test_mv_not_in_biotope_project(runner, tmp_path):
    """Test mv command when not in a biotope project."""
    source_file = tmp_path / "test.csv"
    source_file.write_text("test content")
    destination = tmp_path / "moved.csv"
    
    with runner.isolated_filesystem():
        result = runner.invoke(mv, [str(source_file), str(destination)])
        assert result.exit_code != 0
        assert "Not in a biotope project" in result.output


def test_mv_not_in_git_repo(runner, biotope_project):
    """Test mv command when not in a Git repository."""
    source_file = biotope_project / "test.csv"
    source_file.write_text("test content")
    destination = biotope_project / "moved.csv"
    
    # Change to biotope project directory
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=False):
            result = runner.invoke(mv, [str(source_file), str(destination)])
            assert result.exit_code != 0
            assert "Not in a Git repository" in result.output
    finally:
        os.chdir(original_cwd)


def test_mv_file_not_tracked(runner, biotope_project):
    """Test mv command when file is not tracked."""
    source_file = biotope_project / "test.csv"
    source_file.write_text("test content")
    destination = biotope_project / "moved.csv"
    
    # Change to biotope project directory
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=False):
                result = runner.invoke(mv, [str(source_file), str(destination)])
                assert result.exit_code != 0
                assert "is not tracked" in result.output
    finally:
        os.chdir(original_cwd)



def test_mv_successful_move(runner, biotope_project_with_file):
    """Test successful mv command execution."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    
    # Change to biotope project directory
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes") as mock_stage:
                    result = runner.invoke(mv, [str(source_file), str(destination)])
                    assert result.exit_code == 0
                    assert "Move Complete" in result.output
                    assert "Next steps" in result.output
                    
                    # File should be moved
                    assert not source_file.exists()
                    assert destination.exists()
                    
                    # Git staging should be called
                    mock_stage.assert_called_once()
                    
                    # Metadata should be updated and moved to new location
                    metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "processed" / "test.jsonld"
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                    
                    assert metadata["distribution"][0]["contentUrl"] == "data/processed/test.csv"
                    assert "dateModified" in metadata["distribution"][0]
                    
                    # Original metadata file should no longer exist
                    original_metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "test.jsonld"
                    assert not original_metadata_file.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_force_overwrite(runner, biotope_project_with_file):
    """Test mv command with force overwrite."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "existing.csv"
    
    # Create existing destination file
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("existing content")
    
    # Change to biotope project directory
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [str(source_file), str(destination), "--force"])
                    assert result.exit_code == 0
                    assert "Move Complete" in result.output
                    
                    # File should be moved and overwritten
                    assert not source_file.exists()
                    assert destination.exists()
                    assert destination.read_text() == "gene,expression\nBRCA1,12.5"
    finally:
        os.chdir(original_cwd)


def test_mv_no_metadata_files(runner, biotope_project):
    """Test mv command when no metadata files reference the file."""
    # Create a tracked file but remove its metadata
    source_file = biotope_project / "test.csv"
    source_file.write_text("test content")
    destination = biotope_project / "moved.csv"
    
    # Change to biotope project directory
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                result = runner.invoke(mv, [str(source_file), str(destination)])
                assert result.exit_code == 0
                assert "No metadata files found" in result.output
    finally:
        os.chdir(original_cwd)


def test_mv_creates_destination_directory(runner, biotope_project_with_file):
    """Test that mv creates destination directory structure."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "deep" / "nested" / "structure" / "test.csv"
    
    # Ensure destination directory doesn't exist
    assert not destination.parent.exists()
    
    # Change to biotope project directory
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [str(source_file), str(destination)])
                    assert result.exit_code == 0
                    
                    # Directory should be created
                    assert destination.parent.exists()
                    assert destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_multiple_metadata_files(biotope_project_with_file):
    """Test mv when multiple metadata files reference the same file."""
    # Create second metadata file referencing the same file
    second_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "test_copy",
        "description": "Copy of test dataset",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_87654321",
                "name": "test.csv",
                "contentUrl": "data/raw/test.csv",
                "sha256": "def456",
                "contentSize": 100
            }
        ]
    }
    
    second_metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "test_copy.jsonld"
    with open(second_metadata_file, "w") as f:
        json.dump(second_metadata, f, indent=2)
    
    test_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    metadata_files = _find_metadata_files_for_file(test_file, biotope_project_with_file)
    
    # Should find both metadata files
    assert len(metadata_files) == 2
    metadata_names = {f.name for f in metadata_files}
    assert "test.jsonld" in metadata_names
    assert "test_copy.jsonld" in metadata_names


def test_resolve_destination_path_to_existing_directory():
    """Test _resolve_destination_path when destination is an existing directory."""
    # Setup
    source = Path("/tmp/source.csv")
    destination = Path("/tmp/existing_dir")
    
    # Mock pathlib methods properly
    with mock.patch('pathlib.Path.exists', return_value=True), \
         mock.patch('pathlib.Path.is_dir', return_value=True):
        
        result = _resolve_destination_path(source, destination)
        expected = destination / source.name
        assert result == expected


def test_resolve_destination_path_to_file():
    """Test _resolve_destination_path when destination is a file path."""
    source = Path("/tmp/source.csv")
    destination = Path("/tmp/dest.csv")
    
    # Mock destination as not existing (or not a directory)
    with mock.patch('pathlib.Path.exists', return_value=False):
        result = _resolve_destination_path(source, destination)
        assert result == destination


def test_resolve_destination_path_to_existing_file():
    """Test _resolve_destination_path when destination is an existing file."""
    source = Path("/tmp/source.csv")
    destination = Path("/tmp/existing_file.csv")
    
    # Mock destination as existing file (not directory)
    with mock.patch('pathlib.Path.exists', return_value=True), \
         mock.patch('pathlib.Path.is_dir', return_value=False):
        
        result = _resolve_destination_path(source, destination)
        assert result == destination


def test_mv_to_existing_directory(runner, biotope_project_with_file):
    """Test mv command when destination is an existing directory."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination_dir = biotope_project_with_file / "data" / "processed"
    destination_dir.mkdir(parents=True, exist_ok=True)
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [str(source_file), str(destination_dir)])
                    assert result.exit_code == 0
                    
                    # File should be moved into the directory with same name
                    final_destination = destination_dir / "test.csv"
                    assert final_destination.exists()
                    assert not source_file.exists()
                    
                    # Metadata should be updated
                    metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "processed" / "test.jsonld"
                    assert metadata_file.exists()
    finally:
        os.chdir(original_cwd)


def test_update_metadata_file_path_missing_distribution():
    """Test updating metadata file when distribution field is missing."""
    with mock.patch("biotope.commands.mv.Path") as mock_path:
        mock_file = mock.MagicMock()
        mock_path.return_value = mock_file
        
        # Mock metadata without distribution field
        metadata = {
            "@context": {"@vocab": "https://schema.org/"},
            "@type": "Dataset",
            "name": "test"
        }
        
        with mock.patch("builtins.open", mock.mock_open(read_data=json.dumps(metadata))):
            result = _update_metadata_file_path(
                Path("/fake/metadata.jsonld"),
                "old/path.csv",
                "new/path.csv",
                "checksum",
                Path("/fake/root")
            )
            assert result is False


def test_update_metadata_file_path_empty_distribution():
    """Test updating metadata file when distribution array is empty."""
    with mock.patch("biotope.commands.mv.Path") as mock_path:
        mock_file = mock.MagicMock()
        mock_path.return_value = mock_file
        
        # Mock metadata with empty distribution
        metadata = {
            "@context": {"@vocab": "https://schema.org/"},
            "@type": "Dataset",
            "name": "test",
            "distribution": []
        }
        
        with mock.patch("builtins.open", mock.mock_open(read_data=json.dumps(metadata))):
            result = _update_metadata_file_path(
                Path("/fake/metadata.jsonld"),
                "old/path.csv",
                "new/path.csv",
                "checksum",
                Path("/fake/root")
            )
            assert result is False


def test_update_metadata_file_path_multiple_distributions():
    """Test updating metadata file with multiple distributions, only one matching."""
    biotope_root = Path("/fake/root")
    
    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "test",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "contentUrl": "other/file.csv",
                "sha256": "other_checksum"
            },
            {
                "@type": "sc:FileObject",
                "contentUrl": "old/path.csv",
                "sha256": "old_checksum"
            }
        ]
    }
    
    # Mock the new file's stat for size calculation
    mock_stat = mock.MagicMock()
    mock_stat.st_size = 150
    
    # Create a mock that handles both read and write operations
    read_data = json.dumps(metadata)
    mock_file = mock.mock_open(read_data=read_data)
    
    with mock.patch("builtins.open", mock_file), \
         mock.patch('pathlib.Path.stat', return_value=mock_stat):
        
        result = _update_metadata_file_path(
            Path("/fake/metadata.jsonld"),
            "old/path.csv",
            "new/path.csv",
            "new_checksum",
            biotope_root
        )
        
        assert result is True
        
        # Verify that the file was opened for both reading and writing
        assert mock_file.call_count == 2  # Once for read, once for write


def test_update_metadata_file_path_file_size_error():
    """Test updating metadata file when file size calculation fails."""
    with mock.patch.object(Path, '__truediv__') as mock_div:
        mock_file = mock.MagicMock()
        mock_div.return_value = mock_file
        mock_file.stat.side_effect = OSError("Permission denied")
        
        metadata = {
            "@context": {"@vocab": "https://schema.org/"},
            "@type": "Dataset",
            "name": "test",
            "distribution": [
                {
                    "@type": "sc:FileObject",
                    "contentUrl": "old/path.csv",
                    "sha256": "old_checksum"
                }
            ]
        }
        
        with mock.patch("builtins.open", mock.mock_open(read_data=json.dumps(metadata))):
            result = _update_metadata_file_path(
                Path("/fake/metadata.jsonld"),
                "old/path.csv",
                "new/path.csv",
                "new_checksum",
                Path("/fake/root")
            )
            
            # Should still return False due to exception handling
            assert result is False


def test_update_metadata_file_path_write_permission_error():
    """Test updating metadata file when write permission is denied."""
    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "test",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "contentUrl": "old/path.csv",
                "sha256": "old_checksum"
            }
        ]
    }
    
    # Mock file size calculation
    with mock.patch.object(Path, 'stat') as mock_stat:
        mock_stat.return_value.st_size = 100
        
        # Mock open to succeed for read but fail for write
        mock_open_obj = mock.mock_open(read_data=json.dumps(metadata))
        mock_open_obj.return_value.__enter__.return_value.write.side_effect = IOError("Permission denied")
        
        with mock.patch("builtins.open", mock_open_obj):
            result = _update_metadata_file_path(
                Path("/fake/metadata.jsonld"),
                "old/path.csv",
                "new/path.csv",
                "new_checksum",
                Path("/fake/root")
            )
            
            assert result is False


def test_find_metadata_files_corrupted_json():
    """Test finding metadata files when some contain corrupted JSON."""
    biotope_root = Path("/fake/root")
    
    # Mock the datasets directory structure
    with mock.patch.object(Path, 'exists', return_value=True), \
         mock.patch.object(Path, 'rglob') as mock_rglob:
        
        # Create mock files
        good_file = mock.MagicMock()
        good_file.name = "good.jsonld"
        bad_file = mock.MagicMock()
        bad_file.name = "bad.jsonld"
        
        mock_rglob.return_value = [good_file, bad_file]
        
        # Mock file content
        good_metadata = {
            "distribution": [
                {
                    "@type": "sc:FileObject",
                    "contentUrl": "test/file.csv"
                }
            ]
        }
        
        def mock_open_side_effect(file, *args, **kwargs):
            if file == good_file:
                return mock.mock_open(read_data=json.dumps(good_metadata))()
            else:  # bad_file
                return mock.mock_open(read_data="invalid json")()
        
        with mock.patch("builtins.open", side_effect=mock_open_side_effect):
            test_file = biotope_root / "test" / "file.csv"
            metadata_files = _find_metadata_files_for_file(test_file, biotope_root)
            
            # Should only return the good file
            assert len(metadata_files) == 1
            assert metadata_files[0] == good_file


def test_mv_with_special_characters_in_filename(runner, biotope_project_with_file):
    """Test mv with special characters in filenames."""
    # Create file with special characters
    special_file = biotope_project_with_file / "data" / "raw" / "test file (1) [copy].csv"
    special_file.write_text("gene,expression\nBRCA1,12.5")
    
    # Create corresponding metadata
    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "special_test",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "contentUrl": "data/raw/test file (1) [copy].csv",
                "sha256": "abc123",
                "contentSize": 100
            }
        ]
    }
    
    metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "test file (1) [copy].jsonld"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    
    destination = biotope_project_with_file / "data" / "processed" / "cleaned file.csv"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [str(special_file), str(destination)])
                    assert result.exit_code == 0
                    
                    # File should be moved
                    assert not special_file.exists()
                    assert destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_empty_file(runner, biotope_project_with_file):
    """Test mv with an empty file."""
    # Create empty file
    empty_file = biotope_project_with_file / "data" / "raw" / "empty.csv"
    empty_file.write_text("")
    
    # Create corresponding metadata
    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "empty_test",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "contentUrl": "data/raw/empty.csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "contentSize": 0
            }
        ]
    }
    
    metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "empty.jsonld"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    
    destination = biotope_project_with_file / "data" / "processed" / "empty.csv"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [str(empty_file), str(destination)])
                    assert result.exit_code == 0
                    
                    # File should be moved
                    assert not empty_file.exists()
                    assert destination.exists()
                    assert destination.stat().st_size == 0
    finally:
        os.chdir(original_cwd)


def test_mv_relative_paths(runner, biotope_project_with_file):
    """Test mv command with relative paths."""
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        # Use relative paths
        source_rel = "data/raw/test.csv"
        destination_rel = "data/processed/test.csv"
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [source_rel, destination_rel])
                    assert result.exit_code == 0
                    
                    # Files should be moved using resolved paths
                    source_abs = biotope_project_with_file / "data" / "raw" / "test.csv"
                    dest_abs = biotope_project_with_file / "data" / "processed" / "test.csv"
                    
                    assert not source_abs.exists()
                    assert dest_abs.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_metadata_already_exists_at_destination(runner, biotope_project_with_file):
    """Test mv when metadata file already exists at destination location."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    
    # Create destination metadata file that already exists
    dest_metadata_dir = biotope_project_with_file / ".biotope" / "datasets" / "data" / "processed"
    dest_metadata_dir.mkdir(parents=True, exist_ok=True)
    existing_metadata_file = dest_metadata_dir / "test.jsonld"
    existing_metadata_file.write_text('{"existing": "metadata"}')
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [str(source_file), str(destination)])
                    assert result.exit_code == 0
                    
                    # The existing metadata should be overwritten
                    with open(existing_metadata_file) as f:
                        updated_metadata = json.load(f)
                    
                    # Should contain the updated metadata, not the old "existing" content
                    assert "distribution" in updated_metadata
                    assert updated_metadata["distribution"][0]["contentUrl"] == "data/processed/test.csv"
    finally:
        os.chdir(original_cwd)


def test_execute_move_checksum_calculation_error(biotope_project_with_file):
    """Test _execute_move when checksum calculation fails."""
    from biotope.commands.mv import _execute_move
    from rich.console import Console
    
    source = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    console = Console()
    
    # Mock checksum calculation to fail
    with mock.patch("biotope.commands.mv.calculate_file_checksum", side_effect=OSError("Checksum error")):
        with pytest.raises(click.Abort):
            _execute_move(source, destination, biotope_project_with_file, console)


def test_execute_move_shutil_move_error(biotope_project_with_file):
    """Test _execute_move when shutil.move fails."""
    from biotope.commands.mv import _execute_move
    from rich.console import Console
    
    source = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    console = Console()
    
    # Mock shutil.move to fail
    with mock.patch("biotope.commands.mv.shutil.move", side_effect=OSError("Move failed")):
        with pytest.raises(click.Abort):
            _execute_move(source, destination, biotope_project_with_file, console)


def test_execute_move_metadata_file_move_fails(biotope_project_with_file):
    """Test _execute_move when moving metadata file fails."""
    from biotope.commands.mv import _execute_move
    from rich.console import Console
    
    source = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    console = Console()
    
    # Create destination directory to avoid mkdir issues
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    def mock_move_side_effect(src_str, dst_str):
        # Convert back to Path objects to check content
        src = Path(src_str)
        
        if src.name == "test.csv":
            # Data file move - let it succeed by actually moving the file
            import shutil
            shutil.copy2(src_str, dst_str)  # Copy the file
            Path(src_str).unlink()  # Remove the original
            return None
        elif src.name == "test.jsonld":
            # Metadata file move - make it fail
            raise OSError("Metadata move failed")
        else:
            # Fallback for any other files
            raise OSError("Unexpected file move")
    
    with mock.patch("biotope.commands.mv.shutil.move", side_effect=mock_move_side_effect):
        with mock.patch("biotope.commands.mv.calculate_file_checksum", return_value="new_checksum"):
            with pytest.raises(click.Abort):
                _execute_move(source, destination, biotope_project_with_file, console)


def test_mv_directory_without_recursive_flag(runner, biotope_project_with_file):
    """Test mv command on directory without --recursive flag (should fail)."""
    source_dir = biotope_project_with_file / "data" / "raw"
    destination = biotope_project_with_file / "data" / "processed"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            result = runner.invoke(mv, [str(source_dir), str(destination)])
            assert result.exit_code != 0
            assert "is a directory. Use --recursive (-r)" in result.output
    finally:
        os.chdir(original_cwd)


def test_mv_directory_with_recursive_flag_no_tracked_files(runner, biotope_project):
    """Test mv command on directory with --recursive flag but no tracked files."""
    # Create directory with untracked files
    source_dir = biotope_project / "untracked_dir"
    source_dir.mkdir()
    (source_dir / "untracked.txt").write_text("not tracked")
    
    destination = biotope_project / "moved_dir"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=False):
                result = runner.invoke(mv, [str(source_dir), str(destination), "--recursive"])
                assert result.exit_code != 0
                assert "contains no tracked files" in result.output
    finally:
        os.chdir(original_cwd)


@pytest.fixture
def biotope_project_with_directory(tmp_path):
    """Create biotope project with directory containing multiple tracked files."""
    # Create .biotope structure
    biotope_dir = tmp_path / ".biotope"
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir(parents=True)
    
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    
    # Create test data directory with multiple files
    data_dir = tmp_path / "experiment_data"
    data_dir.mkdir()
    
    # Create multiple test files
    file1 = data_dir / "data1.csv"
    file1.write_text("gene,expression\nBRCA1,12.5")
    
    subdir = data_dir / "subdir"
    subdir.mkdir()
    file2 = subdir / "data2.csv"
    file2.write_text("gene,expression\nBRCA2,8.3")
    
    # Create metadata files
    for file_path, file_id in [(file1, "file_1"), (file2, "file_2")]:
        rel_path = file_path.relative_to(tmp_path)
        metadata = {
            "@context": {"@vocab": "https://schema.org/"},
            "@type": "Dataset",
            "name": f"test_{file_id}",
            "description": f"Dataset for {file_path.name}",
            "distribution": [
                {
                    "@type": "sc:FileObject",
                    "@id": file_id,
                    "name": file_path.name,
                    "contentUrl": str(rel_path),
                    "sha256": f"checksum_{file_id}",
                    "contentSize": 100,
                    "dateCreated": "2023-01-01T00:00:00Z"
                }
            ]
        }
        
        metadata_dir = datasets_dir / rel_path.parent
        metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_file = metadata_dir / f"{file_path.stem}.jsonld"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
    
    return tmp_path


def test_mv_directory_with_recursive_flag_success(runner, biotope_project_with_directory):
    """Test successful mv command on directory with --recursive flag."""
    source_dir = biotope_project_with_directory / "experiment_data"
    destination = biotope_project_with_directory / "moved_experiment"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_directory)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes") as mock_stage:
                    result = runner.invoke(mv, [str(source_dir), str(destination), "--recursive"])
                    assert result.exit_code == 0
                    assert "Directory Move Complete" in result.output
                    assert "Moved 2 tracked file(s)" in result.output
                    
                    # Directory should be moved
                    assert not source_dir.exists()
                    assert destination.exists()
                    
                    # Files should exist in new location
                    assert (destination / "data1.csv").exists()
                    assert (destination / "subdir" / "data2.csv").exists()
                    
                    # Git staging should be called
                    mock_stage.assert_called_once()
                    
                    # Metadata should be updated to new paths
                    metadata1 = biotope_project_with_directory / ".biotope" / "datasets" / "moved_experiment" / "data1.jsonld"
                    metadata2 = biotope_project_with_directory / ".biotope" / "datasets" / "moved_experiment" / "subdir" / "data2.jsonld"
                    
                    assert metadata1.exists()
                    assert metadata2.exists()
                    
                    with open(metadata1) as f:
                        meta1 = json.load(f)
                    assert meta1["distribution"][0]["contentUrl"] == "moved_experiment/data1.csv"
                    
                    with open(metadata2) as f:
                        meta2 = json.load(f)
                    assert meta2["distribution"][0]["contentUrl"] == "moved_experiment/subdir/data2.csv"
    finally:
        os.chdir(original_cwd)


def test_mv_directory_to_existing_directory(runner, biotope_project_with_directory):
    """Test mv directory into existing directory (like mv behavior)."""
    source_dir = biotope_project_with_directory / "experiment_data"
    destination_dir = biotope_project_with_directory / "archive"
    destination_dir.mkdir()
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_directory)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [str(source_dir), str(destination_dir), "--recursive"])
                    assert result.exit_code == 0
                    
                    # Directory should be moved INTO the destination directory
                    final_location = destination_dir / "experiment_data"
                    assert final_location.exists()
                    assert not source_dir.exists()
                    
                    # Files should exist in final location
                    assert (final_location / "data1.csv").exists()
                    assert (final_location / "subdir" / "data2.csv").exists()
    finally:
        os.chdir(original_cwd)


def test_find_tracked_files_in_directory(biotope_project_with_directory):
    """Test _find_tracked_files_in_directory function."""
    
    source_dir = biotope_project_with_directory / "experiment_data"
    
    with mock.patch("biotope.commands.mv.is_file_tracked") as mock_tracked:
        mock_tracked.side_effect = lambda path, root: path.suffix == ".csv"
        
        tracked_files = _find_tracked_files_in_directory(source_dir, biotope_project_with_directory)
        
        assert len(tracked_files) == 2
        file_names = {f.name for f in tracked_files}
        assert "data1.csv" in file_names
        assert "data2.csv" in file_names


def test_mv_directory_mixed_tracked_files(runner, biotope_project_with_directory):
    """Test mv directory with mix of tracked and untracked files."""
    source_dir = biotope_project_with_directory / "experiment_data"
    
    # Add an untracked file
    untracked = source_dir / "untracked.txt"
    untracked.write_text("not tracked")
    
    destination = biotope_project_with_directory / "moved_experiment"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_directory)
        
        def mock_is_tracked(path, root):
            return path.suffix == ".csv"  # Only CSV files are tracked
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", side_effect=mock_is_tracked):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [str(source_dir), str(destination), "--recursive"])
                    assert result.exit_code == 0
                    
                    # All files should be moved (tracked and untracked)
                    assert (destination / "data1.csv").exists()
                    assert (destination / "subdir" / "data2.csv").exists()
                    assert (destination / "untracked.txt").exists()
                    
                    # But only tracked files should have metadata updates
                    assert "Moved 2 tracked file(s)" in result.output
    finally:
        os.chdir(original_cwd)


# New tests for rollback functionality and enhanced error handling

def test_mv_metadata_validation_fails_before_move(runner, biotope_project_with_file):
    """Test mv command when metadata validation fails before file move."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock tempfile operations to fail during validation
                with mock.patch("tempfile.NamedTemporaryFile", side_effect=OSError("Permission denied")):
                    result = runner.invoke(mv, [str(source_file), str(destination)])
                    assert result.exit_code != 0
                    assert "Failed to validate metadata updates" in result.output
                    
                    # File should NOT be moved since validation failed
                    assert source_file.exists()
                    assert not destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_metadata_write_permission_fails_before_move(runner, biotope_project_with_file):
    """Test mv command when metadata write permission fails during validation."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock tempfile operations to fail
                with mock.patch("tempfile.NamedTemporaryFile", side_effect=OSError("Permission denied")):
                    result = runner.invoke(mv, [str(source_file), str(destination)])
                    assert result.exit_code != 0
                    assert "Failed to validate metadata updates" in result.output
                    
                    # File should NOT be moved since validation failed
                    assert source_file.exists()
                    assert not destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_checksum_calculation_failure(runner, biotope_project_with_file):
    """Test mv command rolls back when checksum calculation fails after file move."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock checksum calculation to fail after file move
                with mock.patch("biotope.commands.mv.calculate_file_checksum", side_effect=OSError("Checksum failed")):
                    result = runner.invoke(mv, [str(source_file), str(destination)])
                    assert result.exit_code != 0
                    assert "Failed to calculate checksum" in result.output
                    
                    # File should be rolled back to original location (even without rollback message)
                    assert source_file.exists()
                    assert not destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_metadata_update_failure(runner, biotope_project_with_file):
    """Test mv command when metadata update fails after file move."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock _update_metadata_file_path to fail
                with mock.patch("biotope.commands.mv._update_metadata_file_path", return_value=False):
                    result = runner.invoke(mv, [str(source_file), str(destination)])
                    # Operation should succeed but report 0 updated files
                    assert result.exit_code == 0
                    assert "Updated 0 metadata file(s)" in result.output
                    
                    # File should be moved even if metadata update failed
                    assert not source_file.exists()
                    assert destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_metadata_file_move_failure(runner, biotope_project_with_file):
    """Test mv command rolls back when metadata file move fails after data file move."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock shutil.move to fail only for metadata files
                original_move = shutil.move
                def mock_move_side_effect(src, dst):
                    if "test.jsonld" in str(src):
                        raise OSError("Metadata move failed")
                    # Let data file move succeed by using the original shutil.move
                    return original_move(src, dst)
                
                with mock.patch("biotope.commands.mv.shutil.move", side_effect=mock_move_side_effect):
                    result = runner.invoke(mv, [str(source_file), str(destination)])
                    assert result.exit_code != 0
                    assert "Failed to move metadata file" in result.output
                    assert "Rolling back changes" in result.output
                    
                    # File should be rolled back to original location
                    assert source_file.exists()
                    assert not destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_directory_move_failure(runner, biotope_project_with_directory):
    """Test mv command rolls back when directory move fails."""
    source_dir = biotope_project_with_directory / "experiment_data"
    destination = biotope_project_with_directory / "moved_experiment"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_directory)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock shutil.move to fail for directory move
                with mock.patch("biotope.commands.mv.shutil.move", side_effect=OSError("Directory move failed")):
                    result = runner.invoke(mv, [str(source_dir), str(destination), "--recursive"])
                    assert result.exit_code != 0
                    assert "Failed to move directory" in result.output
                    
                    # Directory should remain in original location
                    assert source_dir.exists()
                    assert not destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_metadata_directory_move_failure(runner, biotope_project_with_directory):
    """Test mv command rolls back when metadata directory move fails during simple rename."""
    source_dir = biotope_project_with_directory / "experiment_data"
    destination = biotope_project_with_directory / "renamed_experiment"
    
    # Ensure this is a simple rename (same parent directory)
    assert source_dir.parent == destination.parent
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_directory)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock shutil.move to fail only for metadata directory move
                original_move = shutil.move
                def mock_move_side_effect(src, dst):
                    if ".biotope" in str(src):
                        raise OSError("Metadata directory move failed")
                    # Let data directory move succeed by using the original shutil.move
                    return original_move(src, dst)
                
                with mock.patch("biotope.commands.mv.shutil.move", side_effect=mock_move_side_effect):
                    result = runner.invoke(mv, [str(source_dir), str(destination), "--recursive"])
                    assert result.exit_code != 0
                    assert "Failed to move metadata directory" in result.output
                    assert "Rolling back changes" in result.output
                    
                    # Directory should be rolled back to original location
                    assert source_dir.exists()
                    assert not destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_checksum_calculation_failure_in_directory_move(runner, biotope_project_with_directory):
    """Test mv command rolls back when checksum calculation fails during directory move."""
    source_dir = biotope_project_with_directory / "experiment_data"
    destination = biotope_project_with_directory / "moved_experiment"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_directory)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock checksum calculation to fail
                with mock.patch("biotope.commands.mv.calculate_file_checksum", side_effect=OSError("Checksum failed")):
                    result = runner.invoke(mv, [str(source_dir), str(destination), "--recursive"])
                    assert result.exit_code != 0
                    assert "Failed to update metadata file" in result.output
                    assert "Rolling back changes" in result.output
                    
                    # Directory should be rolled back to original location
                    assert source_dir.exists()
                    assert not destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_metadata_update_failure_in_directory_move(runner, biotope_project_with_directory):
    """Test mv command when metadata update fails during directory move."""
    source_dir = biotope_project_with_directory / "experiment_data"
    destination = biotope_project_with_directory / "moved_experiment"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_directory)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock _update_metadata_file_path to fail
                with mock.patch("biotope.commands.mv._update_metadata_file_path", return_value=False):
                    result = runner.invoke(mv, [str(source_dir), str(destination), "--recursive"])
                    # Operation should succeed but report 0 updated files
                    assert result.exit_code == 0
                    assert "Updated 0 metadata file(s)" in result.output
                    
                    # Directory should be moved even if metadata update failed
                    assert not source_dir.exists()
                    assert destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_metadata_file_move_failure_in_directory_move(runner, biotope_project_with_directory):
    """Test mv command when metadata file update fails during directory move."""
    source_dir = biotope_project_with_directory / "experiment_data"
    destination = biotope_project_with_directory / "moved_experiment"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_directory)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock _update_metadata_file_path to fail for some files
                def mock_update_side_effect(metadata_file, old_path, new_path, new_checksum, biotope_root):
                    if "data1.jsonld" in str(metadata_file):
                        return False  # Fail for one metadata file
                    return True  # Succeed for others
                
                with mock.patch("biotope.commands.mv._update_metadata_file_path", side_effect=mock_update_side_effect):
                    result = runner.invoke(mv, [str(source_dir), str(destination), "--recursive"])
                    # Operation should succeed but report fewer updated files
                    assert result.exit_code == 0
                    assert "Updated 1 metadata file(s)" in result.output
                    
                    # Directory should be moved even if some metadata updates failed
                    assert not source_dir.exists()
                    assert destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_json_decode_error_in_directory_move(runner, biotope_project_with_directory):
    """Test mv command rolls back when JSON decode error occurs during directory move."""
    source_dir = biotope_project_with_directory / "experiment_data"
    destination = biotope_project_with_directory / "moved_experiment"
    
    # Corrupt one of the metadata files
    corrupted_metadata = biotope_project_with_directory / ".biotope" / "datasets" / "experiment_data" / "data1.jsonld"
    corrupted_metadata.write_text("invalid json content")
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_directory)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                result = runner.invoke(mv, [str(source_dir), str(destination), "--recursive"])
                assert result.exit_code != 0
                assert "Failed to validate metadata updates" in result.output
                
                # Directory should NOT be moved since validation failed
                assert source_dir.exists()
                assert not destination.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_rollback_on_rollback_failure(runner, biotope_project_with_file):
    """Test mv command when rollback itself fails."""
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                # Mock _update_metadata_file_path to fail to trigger rollback
                with mock.patch("biotope.commands.mv._update_metadata_file_path", return_value=False):
                    # Mock shutil.move to fail during rollback
                    with mock.patch("biotope.commands.mv.shutil.move", side_effect=OSError("Rollback failed")):
                        result = runner.invoke(mv, [str(source_file), str(destination)])
                        assert result.exit_code != 0
                        assert "Failed to move file" in result.output
                        
                        # File might be in an inconsistent state
                        # This is expected behavior when rollback fails
    finally:
        os.chdir(original_cwd)


def test_mv_metadata_validation_with_multiple_files(runner, biotope_project_with_file):
    """Test mv command metadata validation with multiple metadata files."""
    # Create a second metadata file referencing the same file
    second_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "test_copy",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "contentUrl": "data/raw/test.csv",
                "sha256": "def456"
            }
        ]
    }
    
    second_metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "test_copy.jsonld"
    with open(second_metadata_file, "w") as f:
        json.dump(second_metadata, f, indent=2)
    
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [str(source_file), str(destination)])
                    assert result.exit_code == 0
                    
                    # Both metadata files should be updated and moved to the new location
                    metadata1 = biotope_project_with_file / ".biotope" / "datasets" / "data" / "processed" / "test.jsonld"
                    metadata2 = biotope_project_with_file / ".biotope" / "datasets" / "data" / "processed" / "test_copy.jsonld"
                    
                    assert metadata1.exists()
                    assert metadata2.exists()
                    
                    # Both should reference the new path
                    with open(metadata1) as f:
                        meta1 = json.load(f)
                    assert meta1["distribution"][0]["contentUrl"] == "data/processed/test.csv"
                    
                    with open(metadata2) as f:
                        meta2 = json.load(f)
                    assert meta2["distribution"][0]["contentUrl"] == "data/processed/test.csv"
                    
                    # Original metadata files should no longer exist
                    original_metadata1 = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "test.jsonld"
                    original_metadata2 = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "test_copy.jsonld"
                    assert not original_metadata1.exists()
                    assert not original_metadata2.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_metadata_validation_with_one_corrupted_file(runner, biotope_project_with_file):
    """Test mv command when one of multiple metadata files is corrupted."""
    # Create a second metadata file referencing the same file
    second_metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "test_copy",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "contentUrl": "data/raw/test.csv",
                "sha256": "def456"
            }
        ]
    }
    
    second_metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "test_copy.jsonld"
    with open(second_metadata_file, "w") as f:
        json.dump(second_metadata, f, indent=2)
    
    # Corrupt the second metadata file
    second_metadata_file.write_text("invalid json content")
    
    source_file = biotope_project_with_file / "data" / "raw" / "test.csv"
    destination = biotope_project_with_file / "data" / "processed" / "test.csv"
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                with mock.patch("biotope.commands.mv.stage_git_changes"):
                    result = runner.invoke(mv, [str(source_file), str(destination)])
                    # Operation should succeed but only update the valid metadata file
                    assert result.exit_code == 0
                    assert "Updated 1 metadata file(s)" in result.output
                    
                    # File should be moved
                    assert not source_file.exists()
                    assert destination.exists()
                    
                    # Only the valid metadata file should be moved
                    valid_metadata = biotope_project_with_file / ".biotope" / "datasets" / "data" / "processed" / "test.jsonld"
                    assert valid_metadata.exists()
                    
                    # Corrupted metadata file should remain in original location
                    corrupted_metadata = biotope_project_with_file / ".biotope" / "datasets" / "data" / "raw" / "test_copy.jsonld"
                    assert corrupted_metadata.exists()
    finally:
        os.chdir(original_cwd)


def test_mv_directory_validation_with_corrupted_metadata(runner, biotope_project_with_directory):
    """Test mv command directory validation when metadata files are corrupted."""
    source_dir = biotope_project_with_directory / "experiment_data"
    destination = biotope_project_with_directory / "moved_experiment"
    
    # Corrupt one of the metadata files
    corrupted_metadata = biotope_project_with_directory / ".biotope" / "datasets" / "experiment_data" / "data1.jsonld"
    corrupted_metadata.write_text("invalid json content")
    
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_directory)
        
        with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                result = runner.invoke(mv, [str(source_dir), str(destination), "--recursive"])
                assert result.exit_code != 0
                assert "Failed to validate metadata updates" in result.output
                
                # Directory should NOT be moved since validation failed
                assert source_dir.exists()
                assert not destination.exists()
    finally:
        os.chdir(original_cwd) 