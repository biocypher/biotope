"""Tests for Git-on-Top commands."""

import json
import subprocess
from unittest.mock import patch

import pytest
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
    def biotope_project(self, tmp_path, monkeypatch):
        """Create a biotope project with Git initialized."""
        monkeypatch.setenv("GIT_AUTHOR_DATE", "2020-01-01T00:00:00Z")
        monkeypatch.setenv("GIT_COMMITTER_DATE", "2020-01-01T00:00:00Z")
        # Create .biotope directory structure
        biotope_dir = tmp_path / ".biotope"
        biotope_dir.mkdir()

        # Create subdirectories
        (biotope_dir / "datasets").mkdir()
        (biotope_dir / "logs").mkdir()

        # Create sample metadata
        metadata = {
            "@context": {"@vocab": "https://schema.org/"},
            "@type": "Dataset",
            "name": "test-dataset",
            "description": "Test dataset",
        }

        with open(biotope_dir / "datasets" / "test.jsonld", "w") as f:
            json.dump(metadata, f)

        # Initialize Git repository
        subprocess.run(["git", "init"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=tmp_path, check=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True)

        return tmp_path

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

    def test_commit_author_amend_and_log_filters(self, runner, biotope_project, monkeypatch):
        monkeypatch.chdir(biotope_project)
        meta = biotope_project / ".biotope" / "datasets" / "new.jsonld"
        meta.write_text('{"name": "new"}')
        result = runner.invoke(commit, ["-m", "Dataset addition", "--author", "Other Author <other@example.org>"])
        assert result.exit_code == 0, result.output
        author = subprocess.check_output(["git", "log", "-1", "--format=%an <%ae>"], text=True).strip()
        assert author == "Other Author <other@example.org>"
        meta.write_text('{"name": "amended"}')
        result = runner.invoke(commit, ["-m", "Amended dataset", "--amend"])
        assert result.exit_code == 0, result.output
        assert subprocess.check_output(["git", "rev-list", "--count", "HEAD"], text=True).strip() == "2"
        result = runner.invoke(log, ["--oneline", "-n", "1"])
        assert result.exit_code == 0, result.output
        assert "Amended dataset" in result.output and "Initial commit" not in result.output
        result = runner.invoke(log, ["--author", "Other Author"])
        assert result.exit_code == 0
        assert "Amended dataset" in result.output and "Initial commit" not in result.output
        for flags in (["--author", "Nobody"], ["--since", "2021-01-01"]):
            result = runner.invoke(log, flags)
            assert result.exit_code == 0
            assert result.output.strip() == "No commits found."

    def test_status_and_log_filter_unrelated_files(self, runner, biotope_project, monkeypatch):
        monkeypatch.chdir(biotope_project)
        (biotope_project / "unrelated.txt").write_text("outside metadata")
        result = runner.invoke(status, ["--porcelain"])
        assert result.exit_code == 0
        assert "unrelated.txt" in result.output
        result = runner.invoke(status, ["--porcelain", "--biotope-only"])
        assert result.exit_code == 0
        assert result.output == ""
        subprocess.run(["git", "add", "unrelated.txt"], check=True)
        subprocess.run(["git", "commit", "-m", "Unrelated change"], check=True, capture_output=True)
        result = runner.invoke(log, ["--oneline"])
        assert "Unrelated change" in result.output
        result = runner.invoke(log, ["--oneline", "--biotope-only"])
        assert result.exit_code == 0
        assert "Initial commit" in result.output and "Unrelated change" not in result.output


class TestGitIntegration:
    """Test Git integration utilities."""

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
        valid_metadata = {"@type": "Dataset", "name": "test"}
        with open(datasets_dir / "valid.jsonld", "w") as f:
            json.dump(valid_metadata, f)

        assert _validate_metadata_files(tmp_path) is True

        # Test with invalid JSON
        with open(datasets_dir / "invalid.jsonld", "w") as f:
            f.write("{ invalid json")

        assert _validate_metadata_files(tmp_path) is False
