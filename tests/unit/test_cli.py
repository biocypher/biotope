"""Test the main CLI functionality."""

from click.testing import CliRunner
from biotope.cli import cli

def test_cli_init():
    """Test init command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['init'])
    assert result.exit_code == 0
    assert "Initializing new BioCypher project..." in result.output

def test_cli_build():
    """Test build command."""
    runner = CliRunner()
    result = runner.invoke(cli, ['build'])
    assert result.exit_code == 0
    assert "Building knowledge representation..." in result.output

def test_cli_version():
    """Test version flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--version'])
    assert result.exit_code == 0
    assert result.output.startswith('cli, version')

def test_cli_with_input():
    """Test CLI with input."""
    runner = CliRunner()
    result = runner.invoke(cli, ['init'], input='y\n')
    assert result.exit_code == 0
    assert "Initializing new BioCypher project..." in result.output

def test_isolated_filesystem():
    """Test read command with file input."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Create a test file
        with open('test.txt', 'w') as f:
            f.write('test content')
        # Test reading from the file
        result = runner.invoke(cli, ['read', '--file', 'test.txt'])
        assert result.exit_code == 0
        assert "Extracted knowledge: test content" in result.output

def test_cli_commands():
    """Test that all main CLI commands are registered."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    # Check that all our commands are listed in help
    for command in ["init", "build", "read", "chat", "view"]:
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
        with open('test.txt', 'w') as f:
            f.write('file content')
        result = runner.invoke(cli, ["read", "--text", "text input", "--file", "test.txt"])
        # File input takes precedence
        assert result.exit_code == 0
        assert "Extracted knowledge: file content" in result.output
