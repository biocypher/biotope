"""Tests for Git-on-Top commands."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from click.testing import CliRunner

from biotope.commands.commit import commit
from biotope.commands.log import log
from biotope.commands.pull import pull
from biotope.commands.push import push
from biotope.commands.status import status


class TestGitCommands:
    """Test Git-on-Top commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    @pytest.fixture
    def biotope_project(self, tmp_path):
        """Create a biotope project with Git initialized."""
        # Create .biotope directory structure
        biotope_dir = tmp_path / ".biotope"
        biotope_dir.mkdir()
        
        # Create subdirectories
        (biotope_dir / "datasets").mkdir()
        (biotope_dir / "config").mkdir()
        (biotope_dir / "logs").mkdir()
        
        # Create sample metadata
        metadata = {
            "@context": {"@vocab": "https://schema.org/"},
            "@type": "Dataset",
            "name": "test-dataset",
            "description": "Test dataset"
        }
        
        with open(biotope_dir / "datasets" / "test.jsonld", "w") as f:
            json.dump(metadata, f)
        
        # Initialize Git repository
        subprocess.run(["git", "init"], cwd=tmp_path, check=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True)
        
        return tmp_path

    def test_commit_success(self, runner, biotope_project):
        """Test successful commit."""
        with patch("biotope.commands.commit.find_biotope_root", return_value=biotope_project):
            # Create a change
            with open(biotope_project / ".biotope" / "datasets" / "new.jsonld", "w") as f:
                json.dump({"name": "new-dataset"}, f)
            
            result = runner.invoke(commit, ["-m", "Add new dataset"])
            
            assert result.exit_code == 0
            assert "Commit" in result.output
            assert "successfully" in result.output

    def test_commit_no_git_repo(self, runner, tmp_path):
        """Test commit without Git repository."""
        with patch("biotope.commands.commit.find_biotope_root", return_value=tmp_path):
            result = runner.invoke(commit, ["-m", "Test"])
            
            assert result.exit_code != 0
            assert "Not in a Git repository" in result.output

    def test_commit_no_changes(self, runner, biotope_project):
        """Test commit with no changes."""
        with patch("biotope.commands.commit.find_biotope_root", return_value=biotope_project):
            result = runner.invoke(commit, ["-m", "No changes"])
            
            assert result.exit_code != 0
            assert "No changes to commit" in result.output

    def test_status_success(self, runner, biotope_project):
        """Test successful status."""
        with patch("biotope.commands.status.find_biotope_root", return_value=biotope_project):
            result = runner.invoke(status)
            
            assert result.exit_code == 0
            assert "Biotope Project Status" in result.output
            assert "Git Repository: ✅" in result.output

    def test_status_no_git_repo(self, runner, tmp_path):
        """Test status without Git repository."""
        with patch("biotope.commands.status.find_biotope_root", return_value=tmp_path):
            result = runner.invoke(status)
            
            assert result.exit_code != 0
            assert "Not in a Git repository" in result.output

    def test_status_porcelain(self, runner, biotope_project):
        """Test status with porcelain output."""
        with patch("biotope.commands.status.find_biotope_root", return_value=biotope_project):
            result = runner.invoke(status, ["--porcelain"])
            
            assert result.exit_code == 0
            # Should be empty since no changes
            assert result.output.strip() == ""

    def test_log_success(self, runner, biotope_project):
        """Test successful log."""
        with patch("biotope.commands.log.find_biotope_root", return_value=biotope_project):
            result = runner.invoke(log)
            
            assert result.exit_code == 0
            assert "commit" in result.output.lower()

    def test_log_no_git_repo(self, runner, tmp_path):
        """Test log without Git repository."""
        with patch("biotope.commands.log.find_biotope_root", return_value=tmp_path):
            result = runner.invoke(log)
            
            assert result.exit_code != 0
            assert "Not in a Git repository" in result.output

    def test_log_oneline(self, runner, biotope_project):
        """Test log with oneline format."""
        with patch("biotope.commands.log.find_biotope_root", return_value=biotope_project):
            result = runner.invoke(log, ["--oneline"])
            
            assert result.exit_code == 0
            # Should show commit hash and message
            assert len(result.output.strip().split()) >= 2

    def test_push_no_remote(self, runner, biotope_project):
        """Test push without remote."""
        with patch("biotope.commands.push.find_biotope_root", return_value=biotope_project):
            result = runner.invoke(push)
            
            assert result.exit_code != 0
            assert "Remote 'origin' not found" in result.output

    def test_pull_no_remote(self, runner, biotope_project):
        """Test pull without remote."""
        with patch("biotope.commands.pull.find_biotope_root", return_value=biotope_project):
            result = runner.invoke(pull)
            
            assert result.exit_code != 0
            assert "Remote 'origin' not found" in result.output

    def test_commit_with_author(self, runner, biotope_project):
        """Test commit with custom author."""
        with patch("biotope.commands.commit.find_biotope_root", return_value=biotope_project):
            # Create a change
            with open(biotope_project / ".biotope" / "datasets" / "author.jsonld", "w") as f:
                json.dump({"name": "author-test"}, f)
            
            result = runner.invoke(commit, ["-m", "Test author", "-a", "Test User <test@example.com>"])
            
            assert result.exit_code == 0
            assert "Commit" in result.output

    def test_commit_amend(self, runner, biotope_project):
        """Test commit with amend flag."""
        with patch("biotope.commands.commit.find_biotope_root", return_value=biotope_project):
            # Create a change
            with open(biotope_project / ".biotope" / "datasets" / "amend.jsonld", "w") as f:
                json.dump({"name": "amend-test"}, f)
            
            result = runner.invoke(commit, ["-m", "Test amend", "--amend"])
            
            assert result.exit_code == 0
            assert "Commit" in result.output

    def test_status_biotope_only(self, runner, biotope_project):
        """Test status with biotope-only flag."""
        with patch("biotope.commands.status.find_biotope_root", return_value=biotope_project):
            result = runner.invoke(status, ["--biotope-only"])
            
            assert result.exit_code == 0
            assert "Biotope Project Status" in result.output

    def test_log_biotope_only(self, runner, biotope_project):
        """Test log with biotope-only flag."""
        with patch("biotope.commands.log.find_biotope_root", return_value=biotope_project):
            result = runner.invoke(log, ["--biotope-only"])
            
            assert result.exit_code == 0
            assert "commit" in result.output.lower()

    def test_log_with_filters(self, runner, biotope_project):
        """Test log with various filters."""
        with patch("biotope.commands.log.find_biotope_root", return_value=biotope_project):
            # Test max count
            result = runner.invoke(log, ["-n", "1"])
            assert result.exit_code == 0
            
            # Test since date
            result = runner.invoke(log, ["--since", "2020-01-01"])
            assert result.exit_code == 0
            
            # Test author filter
            result = runner.invoke(log, ["--author", "test"])
            assert result.exit_code == 0


class TestGitIntegration:
    """Test Git integration utilities."""

    def test_find_biotope_root(self, tmp_path):
        """Test finding biotope root."""
        from biotope.utils import find_biotope_root
        import os
        from unittest.mock import patch
        
        # Should not find biotope root in empty directory
        with patch("biotope.utils.Path.cwd", return_value=tmp_path):
            assert find_biotope_root() is None
        
        # Create .biotope and .git directories (both required)
        biotope_dir = tmp_path / ".biotope"
        biotope_dir.mkdir()
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        # Change to tmp_path and find root
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            assert find_biotope_root() == tmp_path
        finally:
            os.chdir(original_cwd)

    def test_is_git_repo(self, tmp_path):
        """Test Git repository detection."""
        from biotope.utils import is_git_repo
        from unittest.mock import patch, Mock
        # Should not be Git repo
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")
            assert not is_git_repo(tmp_path)
        # Simulate git repo
        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            assert is_git_repo(tmp_path)

    def test_validate_metadata_files(self, tmp_path):
        """Test metadata validation."""
        from biotope.commands.commit import _validate_metadata_files
        
        # Create biotope directory
        biotope_dir = tmp_path / ".biotope"
        datasets_dir = biotope_dir / "datasets"
        datasets_dir.mkdir(parents=True)
        
        # Test with no datasets
        assert _validate_metadata_files(tmp_path) is True
        
        # Test with valid metadata
        valid_metadata = {
            "@type": "Dataset",
            "name": "test"
        }
        with open(datasets_dir / "valid.jsonld", "w") as f:
            json.dump(valid_metadata, f)
        
        assert _validate_metadata_files(tmp_path) is True
        
        # Test with invalid JSON
        with open(datasets_dir / "invalid.jsonld", "w") as f:
            f.write("{ invalid json")
        
        assert _validate_metadata_files(tmp_path) is False 