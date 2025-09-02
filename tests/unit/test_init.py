"""Test the init command functionality."""

from pathlib import Path

import click
import yaml
from click.testing import CliRunner

from biotope.commands.init import init


@click.group()
def cli_test():
    """Test CLI group."""


def test_init_basic():
    """Test basic initialization with default values."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            init,
            input="test-project\nn\nn\nn\ny\n",
            obj={"version": "0.1.0"},
        )
        assert result.exit_code == 0
        assert "Biotope established successfully!" in result.output

        # Check directory structure
        assert Path("config").exists()
        assert Path("data/raw").exists()
        assert Path("data/processed").exists()
        assert Path("schemas").exists()
        assert Path("outputs").exists()
        assert Path(".biotope").exists()

        # Check config file
        with open("config/biotope.yaml") as f:
            config = yaml.safe_load(f)
            assert config["project"]["name"] == "test-project"
            assert config["project"]["output_format"] == "neo4j"
            assert config["knowledge_sources"] == []


def test_init_with_project_metadata():
    """Test initialization with project metadata collection."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Input: project name, no knowledge graph, no LLM, yes to project metadata
        # Then provide some metadata values
        input_data = (
            "test-project\n"  # project name
            "n\n"  # no knowledge graph
            "n\n"  # no LLM
            "y\n"  # yes to project metadata
            "Test project description\n"  # description
            "https://example.com\n"  # URL
            "test@example.com\n"  # creator
            "\n"  # accept default license
            "\n"  # accept default citation
            "n\n"  # no access restrictions
            "n\n"  # no legal obligations
            "n\n"  # no collaboration partner
            "y\n"  # yes to Git
        )

        result = runner.invoke(
            init,
            input=input_data,
            obj={"version": "0.1.0"},
        )
        assert result.exit_code == 0
        assert "Biotope established successfully!" in result.output

        # Check that project metadata was stored
        with open(".biotope/config/biotope.yaml") as f:
            config = yaml.safe_load(f)
            assert "project_metadata" in config
            project_metadata = config["project_metadata"]
            assert project_metadata["description"] == "Test project description"
            assert project_metadata["url"] == "https://example.com"
            assert project_metadata["creator"] == "test@example.com"
            assert "license" in project_metadata
            assert "citation" in project_metadata


def test_init_without_project_metadata():
    """Test initialization without project metadata collection."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Input: project name, no knowledge graph, no LLM, no to project metadata
        input_data = (
            "test-project\n"  # project name
            "n\n"  # no knowledge graph
            "n\n"  # no LLM
            "n\n"  # no to project metadata
            "y\n"  # yes to Git
        )

        result = runner.invoke(
            init,
            input=input_data,
            obj={"version": "0.1.0"},
        )
        assert result.exit_code == 0
        assert "Biotope established successfully!" in result.output

        # Check that no project metadata was stored
        with open(".biotope/config/biotope.yaml") as f:
            config = yaml.safe_load(f)
            assert "project_metadata" not in config


def test_init_with_knowledge_graph():
    """Test initialization with knowledge graph (should show output format)."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Input: project name, yes to knowledge graph, add one source, neo4j output, no LLM, no project metadata
        input_data = (
            "test-project\n"  # project name
            "y\n"  # yes to knowledge graph
            "test-db\n"  # knowledge source name
            "database\n"  # source type
            "\n"  # finish sources
            "neo4j\n"  # output format
            "n\n"  # no LLM
            "n\n"  # no to project metadata
            "y\n"  # yes to Git
        )

        result = runner.invoke(
            init,
            input=input_data,
            obj={"version": "0.1.0"},
        )
        assert result.exit_code == 0
        assert "Biotope established successfully!" in result.output

        # Check that knowledge sources were stored
        with open("config/biotope.yaml") as f:
            config = yaml.safe_load(f)
            assert len(config["knowledge_sources"]) == 1
            assert config["knowledge_sources"][0]["name"] == "test-db"
            assert config["knowledge_sources"][0]["type"] == "database"


def test_init_with_llm():
    """Test initialization with LLM configuration."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Configure with OpenAI
        result = runner.invoke(
            init,
            input="test-project\ny\n\nneo4j\ny\nopenai\nsk-test123\nn\ny\n",
            obj={"version": "0.1.0"},
        )
        assert result.exit_code == 0

        with open("config/biotope.yaml") as f:
            config = yaml.safe_load(f)
            assert "llm" in config
            assert config["llm"]["provider"] == "openai"
            assert config["llm"]["api_key"] == "sk-test123"


def test_init_existing_biotope():
    """Test initialization fails when .biotope directory exists."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create .biotope directory
        Path(".biotope").mkdir()

        result = runner.invoke(init, obj={"version": "0.1.0"})
        assert result.exit_code != 0
        assert "already exists" in result.output


def test_init_in_regular_git_repo():
    """Test initialization works in a regular git repository."""
    import subprocess

    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a proper git repository in current directory
        subprocess.run(["git", "init"], check=True, capture_output=True)

        # Try to init biotope in the same directory (should work)
        result = runner.invoke(
            init,
            input="test-project\nn\nn\nn\n",  # project name, no KG, no LLM, no project metadata, no git
            obj={"version": "0.1.0"},
        )

        assert result.exit_code == 0
        assert "Biotope established successfully!" in result.output

        # Check that biotope project was created
        assert Path(".biotope").exists()
        assert Path("config/biotope.yaml").exists()


def test_init_in_git_submodule():
    """Test initialization works in git submodule (both current and parent have .git)."""
    import subprocess

    runner = CliRunner()
    with runner.isolated_filesystem():
        main_repo = Path("main_repo")
        main_repo.mkdir()

        # Create a proper git repository in the main repo
        subprocess.run(["git", "init"], cwd=main_repo, check=True, capture_output=True)

        # Create a subdirectory with its own git repository (simulating a submodule)
        submodule = main_repo / "submodule"
        submodule.mkdir()
        subprocess.run(["git", "init"], cwd=submodule, check=True, capture_output=True)

        result = runner.invoke(
            init,
            ["--dir", str(submodule)],
            input="test-project\nn\nn\nn\n",  # project name, no KG, no LLM, no project metadata, no git
            obj={"version": "0.1.0"},
        )

        assert result.exit_code == 0
        assert "Biotope established successfully!" in result.output

        # Check that biotope project was created in the submodule
        assert (submodule / ".biotope").exists()
        assert (submodule / "config/biotope.yaml").exists()


def test_init_fails_in_subdirectory_without_git_when_declined():
    """Test initialization fails when user declines to init git in subdirectory."""
    import subprocess
    from unittest.mock import patch

    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a git repository in current directory
        subprocess.run(["git", "init"], check=True, capture_output=True)

        # Create a subdirectory WITHOUT its own .git
        subdir = Path("subproject")
        subdir.mkdir()

        with patch("click.confirm", return_value=False):
            result = runner.invoke(
                init, ["--dir", str(subdir)], obj={"version": "0.1.0"}
            )
            assert result.exit_code != 0
            assert "Found a Git repository in a parent directory" in result.output
            assert (
                "Biotope requires .git and .biotope to be in the same directory"
                in result.output
            )
            assert (
                "Or initialize a Git repository in the current directory to create a Git submodule"
                in result.output
            )


def test_init_succeeds_in_subdirectory_when_git_init_accepted():
    """Test initialization succeeds when user accepts to init git in subdirectory."""
    import subprocess
    from unittest.mock import patch, Mock

    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a git repository in current directory
        subprocess.run(["git", "init"], check=True, capture_output=True)

        # Create a subdirectory WITHOUT its own .git
        subdir = Path("subproject")
        subdir.mkdir()

        # Mock subprocess.run to simulate successful git operations
        def mock_subprocess_run(args, **kwargs):
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            if args[:2] == ["git", "init"]:
                # Create .git directory to simulate successful init
                (subdir / ".git").mkdir()
            elif args[:3] == ["git", "rev-parse", "--git-dir"]:
                # After git init, this should succeed
                if (subdir / ".git").exists():
                    mock_result.stdout = ".git"
                else:
                    mock_result.returncode = 1
            elif args[:2] == ["git", "add"]:
                pass  # Successful git add
            elif args[:2] == ["git", "commit"]:
                mock_result.stdout = "[main abc1234] Initial biotope project setup"
            return mock_result

        # Mock click.confirm to handle different prompts appropriately
        def mock_confirm(prompt, default=None):
            if "initialize a Git repository in the current directory" in prompt:
                return True  # Accept git initialization
            else:
                return False  # Decline other prompts (knowledge graph, LLM, etc.)

        with patch("click.confirm", side_effect=mock_confirm), patch(
            "subprocess.run", side_effect=mock_subprocess_run
        ):
            result = runner.invoke(
                init,
                ["--dir", str(subdir)],
                input="test-project\n",  # just project name, mocks handle the rest
                obj={"version": "0.1.0"},
            )

            assert result.exit_code == 0
            assert "Git repository initialized in current directory" in result.output
            assert "Biotope established successfully!" in result.output

            # Check that biotope project was created
            assert (subdir / ".biotope").exists()
            assert (subdir / "config/biotope.yaml").exists()


def test_init_custom_directory():
    """Test initialization in a custom directory."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            init,
            ["--dir", "custom_dir"],
            input="test-project\ny\n\nneo4j\nn\nn\ny\n",
            obj={"version": "0.1.0"},
        )
        assert result.exit_code == 0
        assert Path("custom_dir/config").exists()
        assert Path("custom_dir/.biotope").exists()


def test_init_metadata():
    """Test metadata file creation and content."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            init,
            input="test-project\ny\n\nneo4j\nn\nn\ny\n",
            obj={"version": "0.1.0"},
        )
        assert result.exit_code == 0

        # Check consolidated biotope config instead of separate metadata file
        with open(".biotope/config/biotope.yaml") as f:
            config = yaml.safe_load(f)
            project_info = config.get("project_info", {})
            assert project_info["name"] == "test-project"
            assert "created_at" in project_info
            assert "biotope_version" in project_info
            assert "last_modified" in project_info
            assert isinstance(project_info["builds"], list)
            assert isinstance(project_info["knowledge_sources"], list)


def test_init_non_interactive():
    """Test initialization with --non-interactive flag uses git user.name and skips prompts."""
    import subprocess

    runner = CliRunner()
    with runner.isolated_filesystem():
        # Initialize a git repo and set a user.name so non-interactive can derive project name
        subprocess.run(["git", "init"], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "ci-user"], check=True, capture_output=True)

        result = runner.invoke(
            init,
            ["--non-interactive"],
            obj={"version": "0.1.0"},
        )

        assert result.exit_code == 0
        # Should announce automatic initialization with derived project name
        assert "Initializing biotope automatically with project name" in result.output

        # Check that config was created with the derived project name
        with open("config/biotope.yaml") as f:
            config = yaml.safe_load(f)
            assert config["project"]["name"] == "ci-user_project"
