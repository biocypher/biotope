"""Supported CLI contract: metadata and mapping, without payload execution."""

import subprocess
import sys


def test_cli_import_does_not_depend_on_readers_or_graph_execution():
    script = """
import sys
class RejectDownstream:
    def find_spec(self, fullname, *args):
        if fullname in {
            'biotope.graph.build',
            'biotope.graph.output',
            'biocypher',
        }:
            raise RuntimeError('unsupported dependency: ' + fullname)
sys.meta_path.insert(0, RejectDownstream())
from biotope.cli import cli
from click.testing import CliRunner
result = CliRunner().invoke(cli, ['map', '--help'])
assert result.exit_code == 0, result.output
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
