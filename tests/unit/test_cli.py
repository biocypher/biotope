"""Test the main CLI functionality."""

from click.testing import CliRunner

from biotope._version import __version__
from biotope.cli import cli


def test_cli_version():
    """Test version flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"biotope, version {__version__}"
