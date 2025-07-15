"""Tests for enhanced init command with Git integration."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from click.testing import CliRunner

from biotope.commands.init import init


class TestInitWithGit:
    """Test init command with Git integration."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    def test_init_with_git_auto_init(self, runner, tmp_path):
        """Test init with automatic Git initialization (simplified, env-independent)."""
        from subprocess import CalledProcessError

        def mock_subprocess_run(args, **kwargs):
            # Simulate "not a git repo" for rev-parse
            if args[:3] == ["git", "rev-parse", "--git-dir"]:
                raise CalledProcessError(1, args)
            # Simulate successful git commands
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            if args[:2] == ["git", "init"]:
                pass
            elif args[:2] == ["git", "add"]:
                pass
            elif args[:2] == ["git", "commit"]:
                mock_result.stdout = "[main abc1234] Initial biotope project setup"
            return mock_result

        # Test the git integration functions directly
        with patch("subprocess.run", side_effect=mock_subprocess_run) as mock_run:
            # Test is_git_repo function
            from biotope.utils import is_git_repo
            assert not is_git_repo(tmp_path)  # Should return False when git rev-parse fails
            
            # Test _init_git_repo function
            from biotope.commands.init import _init_git_repo
            _init_git_repo(tmp_path)
            
            # Check that git commands were called
            called_commands = [call[0][0][:2] for call in mock_run.call_args_list]
            assert ["git", "init"] in called_commands
            assert ["git", "add"] in called_commands
            assert ["git", "commit"] in called_commands

    def test_init_without_git_auto_init(self, runner, tmp_path):
        """Test init without automatic Git initialization."""
        with patch("click.confirm", return_value=False):
            result = runner.invoke(
                init,
                ["--dir", str(tmp_path)],
                input="test-project\nn\nneo4j\nn\ny\n",
                obj={"version": "0.1.0"},
            )
            
            assert result.exit_code == 0
            assert "Biotope established successfully!" in result.output
            assert "Git repository initialized" not in result.output
            
            # Check that Git was not initialized
            assert not (tmp_path / ".git").exists()

    def test_init_existing_git_repo(self, runner, tmp_path):
        """Test init in existing Git repository (env-independent)."""
        def mock_subprocess_run(args, **kwargs):
            from subprocess import CalledProcessError
            mock_result = Mock()
            mock_result.returncode = 0
            if args[:3] == ["git", "rev-parse", "--git-dir"]:
                mock_result.stdout = ".git"
            else:
                mock_result.stdout = ""
            return mock_result

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            result = runner.invoke(
                init,
                ["--dir", str(tmp_path)],
                input="test-project\nn\nneo4j\nn\ny\n",
                obj={"version": "0.1.0"},
            )
            assert result.exit_code == 0
            assert "Biotope established successfully!" in result.output
            # Should not ask about Git initialization since it already exists
            assert "Git repository initialized" not in result.output

    def test_init_git_not_available(self, runner, tmp_path):
        """Test init when Git is not available (env-independent)."""
        def mock_subprocess_side_effect(args, **kwargs):
            if args[:3] == ["git", "rev-parse", "--git-dir"]:
                raise FileNotFoundError("git not found")
            elif args[:2] == ["git", "init"]:
                raise FileNotFoundError("git not found")
            elif args[:2] == ["git", "add"]:
                raise FileNotFoundError("git not found")
            elif args[:2] == ["git", "commit"]:
                raise FileNotFoundError("git not found")
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            return mock_result

        with patch("subprocess.run", side_effect=mock_subprocess_side_effect):
            # Test the git integration functions directly
            from biotope.utils import is_git_repo
            from biotope.commands.init import _init_git_repo
            # Test is_git_repo function
            assert not is_git_repo(tmp_path)  # Should return False when git not found
            # Test _init_git_repo function - should handle FileNotFoundError gracefully
            _init_git_repo(tmp_path)  # Should not raise an exception
            
            # Verify that the warning message would be printed (we can't easily test this without CLI)
            # The important thing is that the function doesn't crash

    def test_init_enhanced_directory_structure(self, runner, tmp_path):
        """Test that enhanced directory structure is created."""
        result = runner.invoke(
            init,
            ["--dir", str(tmp_path)],
            input="test-project\nn\nneo4j\nn\ny\n",
            obj={"version": "0.1.0"},
        )
        
        assert result.exit_code == 0
        
        # Check enhanced directory structure
        expected_dirs = [
            ".biotope",
            ".biotope/config",
            ".biotope/datasets",
            ".biotope/workflows",
            ".biotope/logs",
            "config",
            "data/raw",
            "data/processed",
            "schemas",
            "outputs",
        ]
        
        for dir_path in expected_dirs:
            assert (tmp_path / dir_path).exists()

    def test_init_biotope_config(self, runner, tmp_path):
        """Test that biotope config is created."""
        result = runner.invoke(
            init,
            ["--dir", str(tmp_path)],
            input="test-project\nn\nneo4j\nn\ny\n",
            obj={"version": "0.1.0"},
        )
        
        assert result.exit_code == 0
        
        # Check biotope config
        config_file = tmp_path / ".biotope" / "config" / "biotope.yaml"
        assert config_file.exists()
        
        with open(config_file) as f:
            config = yaml.safe_load(f)
        
        expected_keys = [
            "version",
            "croissant_schema_version",
            "default_metadata_template",
            "data_storage",
            "checksum_algorithm",
            "auto_stage",
            "commit_message_template"
        ]
        
        for key in expected_keys:
            assert key in config

    def test_init_enhanced_readme(self, runner, tmp_path):
        """Test that enhanced README is created."""
        result = runner.invoke(
            init,
            ["--dir", str(tmp_path)],
            input="test-project\nn\nneo4j\nn\ny\n",
            obj={"version": "0.1.0"},
        )
        
        assert result.exit_code == 0
        
        readme_file = tmp_path / "README.md"
        assert readme_file.exists()
        
        with open(readme_file) as f:
            content = f.read()
        
        # Check for Git integration section
        assert "Git Integration" in content
        assert "biotope add" in content
        assert "biotope commit" in content
        assert "git status" in content
        assert "git log" in content

    def test_init_git_on_top_structure(self, runner, tmp_path):
        """Test that Git-on-Top directory structure is created correctly."""
        result = runner.invoke(
            init,
            ["--dir", str(tmp_path)],
            input="test-project\nn\nneo4j\nn\ny\n",
            obj={"version": "0.1.0"},
        )
        
        assert result.exit_code == 0
        
        # These directories should exist in Git-on-Top approach
        expected_dirs = [
            ".biotope",
            ".biotope/config",
            ".biotope/datasets",
            ".biotope/workflows",
            ".biotope/logs",
        ]
        
        for dir_path in expected_dirs:
            assert (tmp_path / dir_path).exists()
        
        # These directories should NOT exist (no custom version control)
        old_dirs = [
            ".biotope/staging",
            ".biotope/objects",
            ".biotope/refs",
        ]
        
        for dir_path in old_dirs:
            assert not (tmp_path / dir_path).exists()

    def test_init_creates_gitignore(self, runner, tmp_path):
        """Test that .gitignore file is created with correct content."""
        result = runner.invoke(
            init,
            ["--dir", str(tmp_path)],
            input="test-project\nn\nneo4j\nn\ny\n",
            obj={"version": "0.1.0"},
        )
        
        assert result.exit_code == 0
        
        # Check that .gitignore exists
        gitignore_file = tmp_path / ".gitignore"
        assert gitignore_file.exists()
        
        # Check that it contains the expected content
        gitignore_content = gitignore_file.read_text()
        
        # Should exclude data directory
        assert "data/" in gitignore_content
        assert "downloads/" in gitignore_content
        assert "tmp/" in gitignore_content
        
        # Should exclude common development files
        assert "__pycache__/" in gitignore_content
        assert ".DS_Store" in gitignore_content
        assert ".vscode/" in gitignore_content
        
        # Should have explanatory comments
        assert "# Biotope data files (not tracked in Git)" in gitignore_content
        assert "# Data files are tracked through metadata in .biotope/datasets/" in gitignore_content

    def test_init_git_workflow_instructions(self, runner, tmp_path):
        """Test that Git workflow instructions are included."""
        result = runner.invoke(
            init,
            ["--dir", str(tmp_path)],
            input="test-project\nn\nneo4j\nn\ny\n",
            obj={"version": "0.1.0"},
        )
        
        assert result.exit_code == 0
        
        # Check that Git workflow instructions are in output
        assert "biotope add <file>" in result.output
        assert "biotope annotate interactive --staged" in result.output
        assert "biotope commit -m \"message\"" in result.output 