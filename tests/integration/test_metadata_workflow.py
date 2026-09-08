"""Supported CLI contract: metadata and mapping, without payload execution."""

import json
import subprocess
import sys

import pytest
import yaml
from click.testing import CliRunner

from biotope.cli import cli
from biotope.croissant import api


def test_removed_commands_and_sample_options_are_rejected(tmp_path):
    runner = CliRunner(mix_stderr=False)
    for command in ("get", "search", "discover", "read"):
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 2, result.output
        assert "No such command" in result.stderr
    result = runner.invoke(cli, ["annotate", "load", "--help"])
    assert result.exit_code == 2
    assert "No such command" in result.stderr
    assert not hasattr(api, "discover_sources")
    result = runner.invoke(cli, ["check-data", "--fix"])
    assert result.exit_code == 2
    assert "No such option" in result.stderr
    manifest = tmp_path / "metadata.jsonld"
    manifest.write_text('{"name": "metadata"}')
    for command, option in (("inspect", "--preview-rows"), ("scaffold", "--preview-rows"), ("preview", "--rows")):
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
            'biotope.croissant.mapping.compile',
            'biotope.croissant.alignment.merge',
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


def test_metadata_to_mapping_and_wizard_with_missing_payloads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".biotope").mkdir()
    (tmp_path / ".biotope" / "project.yaml").write_text("name: offline\n")
    manifest = tmp_path / "metadata.jsonld"
    manifest.write_text(
        json.dumps(
            {
                "name": "offline",
                "distribution": [{"@type": "cr:FileObject", "@id": "source", "contentUrl": "missing.csv"}],
                "recordSet": [
                    {
                        "@id": "genes",
                        "name": "genes",
                        "field": [
                            {"name": "gene_id", "dataType": "sc:Text", "source": {"fileObject": {"@id": "source"}}},
                        ],
                    }
                ],
            }
        )
    )
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(cli, ["map", "--purpose", "Describe genes", "--entity", "gene"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(cli, ["map", "inspect", str(manifest), "--json"])
    assert result.exit_code == 0, result.output
    inspected = json.loads(result.stdout)
    assert inspected["record_sets"][0]["fields"][0]["name"] == "gene_id"
    assert "sample" not in result.output.lower()
    result = runner.invoke(cli, ["map", "scaffold", str(manifest), "--stdout"])
    assert result.exit_code == 0, result.output
    assert "sample" not in result.output.lower()
    draft = yaml.safe_load(result.output)
    draft["entities"]["gene"] = {"record_set": "genes", "id": "gene_id"}
    (tmp_path / "mappings").mkdir()
    mapping = tmp_path / "mappings" / "genes.mapping.yaml"
    mapping.write_text(yaml.safe_dump(draft))
    result = runner.invoke(cli, ["map", "preview", str(mapping), "--json"])
    assert result.exit_code == 0, result.output
    checked = json.loads(result.stdout)["mappings"][mapping.name]
    assert checked["resolved_slots"] == ["entities.gene"]
    assert checked["findings"] == []
    assert "samples" not in checked
    result = runner.invoke(cli, ["map", "--mapping", str(mapping)], input="3\n4\n")
    assert result.exit_code == 0, result.output
    assert "Projected schema" in result.output
    assert "sample" not in mapping.read_text().lower()
    assert not (tmp_path / "missing.csv").exists()
    result = runner.invoke(cli, ["map"], input="q\n")
    assert result.exit_code == 0, result.output
    assert "All slots resolved" in result.output
    assert "biotope build" not in result.output
    # Project-wide validation must not reach the abandoned build command.
    import builtins

    original_import = builtins.__import__

    def without_build(name, *args, **kwargs):
        if name == "biotope.commands.build":
            raise RuntimeError("mapping depends on downstream build")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_build)
    result = runner.invoke(cli, ["map", "preview", "--json"])
    assert result.exit_code == 0, (result.output, result.exception)
    assert list(json.loads(result.stdout)["mappings"]) == [mapping.name]


@pytest.mark.parametrize(
    "entity, ids, expected",
    [
        ({"record_set": "genes", "id": {"use": "key"}}, {"key": {"field": "absent"}}, "absent"),
        ({"record_set": "genes", "id": {"use": "key"}}, {"key": {"use": "key"}}, "cyclic"),
        ({"record_set": "genes"}, {}, "unresolved"),
    ],
)
def test_structural_validation_reports_invalid_bindings(tmp_path, entity, ids, expected):
    manifest = tmp_path / "metadata.jsonld"
    manifest.write_text(
        json.dumps({"recordSet": [{"name": "genes", "field": [{"name": "id", "dataType": "sc:Text"}]}]})
    )
    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(yaml.safe_dump({"croissant": str(manifest), "entities": {"gene": entity}, "ids": ids}))
    result = CliRunner(mix_stderr=False).invoke(cli, ["map", "preview", str(mapping), "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["validation_scope"] == "metadata and mapping definitions; values and transformations are not checked"
    assert expected in result.stdout.lower()
    assert "entities.gene" in result.stdout


@pytest.mark.parametrize("problem", ["endpoint", "yaml"])
def test_malformed_mapping_has_actionable_cli_error(tmp_path, monkeypatch, problem):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".biotope").mkdir()
    (tmp_path / ".biotope/project.yaml").write_text("name: review\n")
    mapping = tmp_path / "broken.mapping.yaml"
    if problem == "yaml":
        mapping.write_text("croissant: [unterminated\n")
        expected = "line 2"
    else:
        mapping.write_text(
            yaml.safe_dump(
                {
                    "croissant": "missing.jsonld",
                    "entities": {"sample": {}},
                    "relations": {"same_sample": {"target": {"entity": "sample", "value": "geo:GSM1"}}},
                }
            )
        )
        expected = "relations.same_sample.target.value"
    runner = CliRunner(mix_stderr=False)
    for command in (
        ["map", "preview", str(mapping)],
        ["map", "defer-relation", str(mapping), "same_sample"],
        ["map", "--mapping", str(mapping)],
    ):
        result = runner.invoke(cli, command)
        assert result.exit_code != 0
        assert isinstance(result.exception, SystemExit), repr(result.exception)
        assert str(mapping) in result.stderr
        assert expected in result.stderr
        assert "Traceback" not in result.stderr
        if problem == "endpoint":
            assert "ids" in result.stderr and "use" in result.stderr


@pytest.mark.parametrize(
    "body",
    [
        "  gap:\n    scan: row  # scan rationale\n",
        "  gap: {scan: row}  # flow rationale\n",
    ],
)
def test_deferral_preserves_authored_yaml(tmp_path, body):
    path = tmp_path / "commented.mapping.yaml"
    original = "# Research purpose\ncroissant: missing.jsonld\nrelations:\n" + body + "# Keep this gap visible\n"
    path.write_text(original)
    runner = CliRunner()
    for command, value in (("defer-relation", True), ("undefer-relation", False)):
        result = runner.invoke(cli, ["map", command, str(path), "gap"])
        assert result.exit_code == 0, result.output
        changed = path.read_text()
        assert yaml.safe_load(changed)["relations"]["gap"]["deferred"] is value
        for comment in (
            "# Research purpose",
            "# Keep this gap visible",
            "# scan rationale" if "scan rationale" in body else "# flow rationale",
        ):
            assert comment in changed
        assert ("{scan: row" in changed) == ("{scan: row" in body)
        # Repeating the edit must not duplicate keys or change the document.
        result = runner.invoke(cli, ["map", command, str(path), "gap"])
        assert result.exit_code == 0, result.output
        assert path.read_text() == changed


def test_deferral_does_not_change_another_relation_through_alias(tmp_path):
    mapping = tmp_path / "aliased.mapping.yaml"
    text = "croissant: absent.jsonld\nrelations:\n  first: &shared {scan: row}\n  second: *shared\n"
    mapping.write_text(text)
    result = CliRunner().invoke(cli, ["map", "defer-relation", str(mapping), "second"])
    assert result.exit_code != 0
    assert "alias" in result.output.lower()
    assert mapping.read_text() == text
