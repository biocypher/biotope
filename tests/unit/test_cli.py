"""Test the main CLI functionality."""

from click.testing import CliRunner

from biotope.cli import cli


def test_cli_build_requires_project():
    """`biotope build` fails cleanly when run outside a project."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["build"])
    assert result.exit_code != 0
    assert "No project.yaml" in result.output


def test_cli_version():
    """Test version flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("cli, version")


def test_isolated_filesystem():
    """Test read command with file input."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a test file
        with open("test.txt", "w") as f:
            f.write("test content")
        # Test reading from the file
        result = runner.invoke(cli, ["read", "--file", "test.txt"])
        assert result.exit_code == 0
        assert "Extracted knowledge: test content" in result.output


def test_cli_commands():
    """Test that all main CLI commands are registered."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    # Check that all our commands are listed in help
    for command in ["init", "build", "read", "view"]:
        assert command in result.output


def test_read_command_text():
    """Test the read command with text input."""
    runner = CliRunner()
    result = runner.invoke(cli, ["read", "--text", "test input"])
    assert result.exit_code == 0
    assert "Extracted knowledge: test input" in result.output


def test_read_command_no_input():
    """Test read command fails without any input."""
    runner = CliRunner()
    result = runner.invoke(cli, ["read"])
    assert result.exit_code != 0
    assert "Either --text or --file must be provided" in result.output


def test_read_command_both_inputs():
    """Test read command with both inputs provided."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("test.txt", "w") as f:
            f.write("file content")
        result = runner.invoke(
            cli,
            ["read", "--text", "text input", "--file", "test.txt"],
        )
        # File input takes precedence
        assert result.exit_code == 0
        assert "Extracted knowledge: file content" in result.output
