"""Integration tests for the get command workflow."""

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest
import requests
from click.testing import CliRunner
import os


@pytest.fixture
def biotope_project(tmp_path):
    """Create a temporary biotope project for integration testing."""
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
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_dir, check=True)
    
    return project_dir


@pytest.fixture
def sample_data_file(tmp_path):
    """Create a sample data file for testing."""
    data_file = tmp_path / "sample_data.csv"
    content = """GeneID,Expression,Status
BRCA1,12.5,High
TP53,8.7,Medium
EGFR,15.2,High"""
    data_file.write_text(content)
    return data_file


def test_get_command_full_workflow(biotope_project, sample_data_file):
    """Test the complete get command workflow."""
    from biotope.commands.get import get
    
    runner = CliRunner()
    
    # Mock the download to return our sample file
    with mock.patch("biotope.commands.get.download_file") as mock_download:
        # Copy sample file to data/raw directory within the biotope project
        data_raw_dir = biotope_project / "data" / "raw"
        data_raw_dir.mkdir(parents=True)
        downloaded_file = data_raw_dir / "sample_data.csv"
        downloaded_file.write_text(sample_data_file.read_text())
        
        mock_download.return_value = downloaded_file
        
        # Run get command
        with mock.patch("biotope.commands.get.find_biotope_root", return_value=biotope_project):
            with mock.patch("biotope.utils.is_git_repo", return_value=True):
                result = runner.invoke(get, ["https://example.com/sample_data.csv"])
        
        assert result.exit_code == 0
        assert "✅ Downloaded:" in result.output
        assert "✅ File added to biotope project" in result.output
        
        # Check that the file was actually added to the biotope project
        datasets_dir = biotope_project / ".biotope" / "datasets"
        
        # Should have a metadata file
        metadata_files = list(datasets_dir.rglob("*.jsonld"))
        assert len(metadata_files) == 1
        
        # Check metadata content
        with open(metadata_files[0]) as f:
            metadata = json.load(f)
        
        assert metadata["@type"] == "Dataset"
        assert "sample_data" in metadata["name"]
        assert len(metadata["distribution"]) == 1
        assert metadata["distribution"][0]["name"] == "sample_data.csv"
        assert "sha256" in metadata["distribution"][0]
        
        # Check Git status
        git_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=biotope_project,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Should have staged changes in .biotope/
        assert ".biotope/" in git_status.stdout


def test_get_command_with_no_add_flag(biotope_project, sample_data_file):
    """Test get command with --no-add flag."""
    from biotope.commands.get import get
    
    runner = CliRunner()
    
    with mock.patch("biotope.commands.get.download_file") as mock_download:
        data_raw_dir = biotope_project / "data" / "raw"
        data_raw_dir.mkdir(parents=True)
        downloaded_file = data_raw_dir / "sample_data.csv"
        downloaded_file.write_text(sample_data_file.read_text())
        
        mock_download.return_value = downloaded_file
        
        with mock.patch("biotope.commands.get.find_biotope_root", return_value=biotope_project):
            with mock.patch("biotope.utils.is_git_repo", return_value=True):
                result = runner.invoke(get, ["https://example.com/sample_data.csv", "--no-add"])
        
        assert result.exit_code == 0
        assert "✅ Downloaded:" in result.output
        assert "📁 Adding file to biotope project..." not in result.output
        assert "File downloaded. To add to biotope project:" in result.output
        
        # Check that no metadata was created
        datasets_dir = biotope_project / ".biotope" / "datasets"
        metadata_files = list(datasets_dir.rglob("*.jsonld"))
        assert len(metadata_files) == 0


def test_get_command_custom_output_directory(biotope_project, sample_data_file):
    """Test get command with custom output directory."""
    from biotope.commands.get import get
    
    runner = CliRunner()
    
    custom_dir = biotope_project / "custom_downloads"
    
    with mock.patch("biotope.commands.get.download_file") as mock_download:
        downloaded_file = custom_dir / "sample_data.csv"
        downloaded_file.parent.mkdir(parents=True, exist_ok=True)
        downloaded_file.write_text(sample_data_file.read_text())
        
        mock_download.return_value = downloaded_file
        
        with mock.patch("biotope.commands.get.find_biotope_root", return_value=biotope_project):
            with mock.patch("biotope.utils.is_git_repo", return_value=True):
                result = runner.invoke(get, [
                    "https://example.com/sample_data.csv",
                    "--output-dir", str(custom_dir)
                ])
        
        assert result.exit_code == 0
        assert "✅ Downloaded:" in result.output
        
        # Check that the file was downloaded to the custom directory
        assert downloaded_file.exists()
        
        # Check that the file was added to biotope project
        datasets_dir = biotope_project / ".biotope" / "datasets"
        metadata_files = list(datasets_dir.rglob("*.jsonld"))
        assert len(metadata_files) == 1


def test_get_command_download_failure(biotope_project):
    """Test get command when download fails."""
    from biotope.commands.get import get
    
    runner = CliRunner()
    
    with mock.patch("biotope.commands.get.download_file", return_value=None):
        with mock.patch("biotope.commands.get.find_biotope_root", return_value=biotope_project):
            with mock.patch("biotope.utils.is_git_repo", return_value=True):
                result = runner.invoke(get, ["https://example.com/nonexistent.csv"])
        
        assert result.exit_code == 1
        assert "❌ Failed to download file" in result.output


def test_get_command_not_in_biotope_project(tmp_path):
    """Test get command when not in a biotope project."""
    from biotope.commands.get import get
    
    runner = CliRunner()
    
    with mock.patch("biotope.commands.get.find_biotope_root", return_value=None):
        result = runner.invoke(get, ["https://example.com/test.csv"])
    
    assert result.exit_code == 1
    assert "❌ Not in a biotope project" in result.output


def test_get_command_not_in_git_repo(biotope_project):
    """Test get command when not in a Git repository."""
    from biotope.commands.get import get
    
    runner = CliRunner()
    
    # Remove .git directory to simulate non-Git repository
    git_dir = biotope_project / ".git"
    if git_dir.exists():
        import shutil
        shutil.rmtree(git_dir)
    
    with mock.patch("biotope.commands.get.find_biotope_root", return_value=biotope_project):
        result = runner.invoke(get, ["https://example.com/test.csv"])
    
    assert result.exit_code == 1
    assert "❌ Not in a Git repository" in result.output


def test_get_command_with_content_disposition_header(biotope_project):
    """Test get command with Content-Disposition header."""
    from biotope.commands.get import get
    
    runner = CliRunner()
    
    # Mock the download function to actually create the file
    def mock_download(url, output_dir):
        custom_file = output_dir / "custom_filename.csv"
        custom_file.write_text("test,data\n1,2\n3,4")
        return custom_file
    
    old_cwd = os.getcwd()
    os.chdir(biotope_project)
    try:
        with mock.patch("biotope.commands.get.download_file", side_effect=mock_download):
            with mock.patch("biotope.commands.get.find_biotope_root", return_value=biotope_project):
                with mock.patch("biotope.utils.is_git_repo", return_value=True):
                    result = runner.invoke(get, ["https://example.com/data"])
        
        assert result.exit_code == 0
        assert "✅ Downloaded:" in result.output
        
        # Check that the file was downloaded with the custom filename
        data_raw_dir = biotope_project / "data" / "raw"
        custom_file = data_raw_dir / "custom_filename.csv"
        assert custom_file.exists()
        
        # Check that it was added to biotope project
        datasets_dir = biotope_project / ".biotope" / "datasets"
        metadata_files = list(datasets_dir.rglob("*.jsonld"))
        assert len(metadata_files) == 1
        
        with open(metadata_files[0]) as f:
            metadata = json.load(f)
        
        assert metadata["distribution"][0]["name"] == "custom_filename.csv"
    finally:
        os.chdir(old_cwd) 