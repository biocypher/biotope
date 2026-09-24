"""Curated metadata: registration, protection from rebakes, replacement reports and atomic writes."""

import json

from click.testing import CliRunner

from biotope.cli import cli
from biotope.graph.sources import register_metadata, write_text_atomic


def test_rebake_stops_before_overwriting_curated_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", ".", "--no-git", "--no-prompt"]).exit_code == 0
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.csv").write_text("id\n1\n")
    authored = tmp_path / "authored.jsonld"
    authored.write_text(json.dumps({"name": "raw", "recordSet": []}))
    target = register_metadata(tmp_path, authored, "raw", reason="Unresolved; preserve review")
    before = target.read_bytes()
    result = runner.invoke(cli, ["add", "raw", "--rebake"])
    assert result.exit_code != 0
    assert "curated" in result.output.lower()
    assert target.read_bytes() == before
    (raw / "b.csv").write_text("new_field\nvalue\n")
    fresh = tmp_path / "review/raw.jsonld"
    result = runner.invoke(cli, ["add", "raw", "--bake-to", str(fresh)])
    assert result.exit_code == 0, result.output
    assert target.read_bytes() == before
    assert not (raw / ".biotope.yaml").exists()
    assert len(json.loads(fresh.read_text())["recordSet"]) == 2
    reviewed = json.loads(fresh.read_text())
    reviewed["description"] = "Reconciled with authored corrections"
    fresh.write_text(json.dumps(reviewed))
    register = ["source", "register", str(fresh), "--name", "raw", "--reason", "Reconciled"]
    refused = runner.invoke(cli, register)
    assert refused.exit_code != 0 and "already exists" in refused.output
    result = runner.invoke(cli, [*register, "--replace"])
    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text())["description"] == reviewed["description"]
    for destination in (fresh, target, raw / "new.jsonld"):
        result = runner.invoke(cli, ["add", "raw", "--bake-to", str(destination)])
        assert result.exit_code != 0


def test_atomic_artifacts_respect_creation_and_existing_permissions(tmp_path):
    ordinary, artifact = tmp_path / "ordinary", tmp_path / "artifact"
    ordinary.write_text("ordinary")
    write_text_atomic(artifact, "new")
    assert artifact.stat().st_mode & 0o777 == ordinary.stat().st_mode & 0o777
    artifact.chmod(0o640)
    write_text_atomic(artifact, "replacement")
    assert artifact.stat().st_mode & 0o777 == 0o640
    assert artifact.read_text() == "replacement"


def test_replacement_reports_lost_annotations_and_nested_field_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".biotope").mkdir()
    reviewed = tmp_path / "reviewed.jsonld"
    reviewed.write_text(
        json.dumps(
            {
                "name": "study",
                "citation": "Reviewed citation 2026",
                "biotope:curation": {"annotation_review": "Citation and fields reviewed"},
                "recordSet": [
                    {
                        "@id": "rows",
                        "field": {
                            "@id": "rows/details",
                            "subField": [
                                {"@id": "rows/details/kept", "dataType": "sc:Text"},
                                {"@id": "rows/details/removed", "dataType": "sc:Text"},
                            ],
                        },
                    },
                    {"@id": "removed-table", "field": [{"@id": "removed-table/id"}]},
                ],
            }
        )
    )
    target = register_metadata(tmp_path, reviewed, "study", reason="Reviewed")
    assert json.loads(target.read_text())["biotope:curation"]["annotation_review"]
    replacement = json.loads(reviewed.read_text())
    del replacement["citation"], replacement["biotope:curation"]
    replacement["recordSet"].pop()
    replacement["recordSet"][0]["field"]["subField"].pop()
    reviewed.write_text(json.dumps(replacement))
    args = ["source", "register", str(reviewed), "--name", "study", "--reason", "Kept everything", "--replace"]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    for lost in ("citation", "annotation_review", "removed-table", "removed-table/id", "rows/details/removed"):
        assert lost in result.output
    assert "rows/details/kept" not in result.output
    assert "citation" not in json.loads(target.read_text())
    again = CliRunner().invoke(cli, args)
    assert again.exit_code == 0 and "drops" not in again.output
