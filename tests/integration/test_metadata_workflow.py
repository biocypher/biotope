"""Supported CLI contract: metadata and mapping, without payload execution."""

import subprocess
import sys

from click.testing import CliRunner

from biotope.cli import cli


def test_removed_commands_and_sample_options_are_rejected(tmp_path):
    runner = CliRunner(mix_stderr=False)
    for command in ("get", "search", "discover", "read", "propose-alignment", "propose-mapping"):
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 2, result.output
        assert "No such command" in result.stderr
    result = runner.invoke(cli, ["annotate", "load", "--help"])
    assert result.exit_code == 2
    assert "No such command" in result.stderr
    result = runner.invoke(cli, ["check-data", "--fix"])
    assert result.exit_code == 2
    assert "No such option" in result.stderr
    manifest = tmp_path / "metadata.jsonld"
    manifest.write_text('{"name": "metadata"}')
    for command, option in (("inspect", "--preview-rows"),):
        result = runner.invoke(cli, ["map", command, str(manifest), option, "1"])
        assert result.exit_code == 2, result.output
        assert "No such option" in result.stderr


def test_cli_import_does_not_depend_on_readers_or_graph_execution():
    script = """
import sys
class RejectDownstream:
    def find_spec(self, fullname, *args):
        if fullname in {
            'biotope.croissant.acquisition.context',
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


def test_no_git_project_can_describe_and_track_metadata(tmp_path, monkeypatch):
    from biotope.validation import get_staged_metadata_files

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    parent_manifest = tmp_path / ".biotope/datasets/parent.jsonld"
    parent_manifest.parent.mkdir(parents=True)
    parent_manifest.write_text("{}")
    subprocess.run(["git", "add", ".biotope"], cwd=tmp_path, check=True)
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.chdir(root)
    runner = CliRunner()
    r = runner.invoke(cli, ["init", ".", "--no-git", "--no-prompt"])
    assert r.exit_code == 0, r.output
    for args in (["status"], ["queue", "--json"], ["check-data"]):
        r = runner.invoke(cli, args)
        assert r.exit_code == 0, (args, r.output, r.exception)
    assert not (root / ".biotope/datasets").exists()
    (root / "raw").mkdir()
    (root / "raw" / "genes.csv").write_text("id,name\n1,A\n")
    for args in (
        ["add", "raw"],
        ["annotate", "apply", "raw", "--set", "description=Reviewed"],
        ["queue", "--json"],
        ["mark", "raw", "mapped"],
        ["status"],
    ):
        r = runner.invoke(cli, args)
        assert r.exit_code == 0, (args, r.output, r.exception)
    assert (root / ".biotope/datasets/raw.jsonld").is_file()
    for directory in ("data", "mappings", ".biotope/workflows"):
        assert not (root / directory).exists()
    assert not (root / ".git").exists()
    assert get_staged_metadata_files(root) == []
    r = runner.invoke(cli, ["rm", "raw", "--keep-data", "--force"])
    assert r.exit_code == 0, r.output
    assert (root / "raw/genes.csv").is_file()
    assert not (root / ".biotope/datasets/raw.jsonld").exists()
    assert (
        subprocess.run(
            ["git", "diff", "--cached", "--name-only"], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout
        == ".biotope/datasets/parent.jsonld\n"
    )
