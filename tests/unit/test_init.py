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
