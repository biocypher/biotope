from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from biotope.commands.init import init
from biotope.commands.map import map_group


def test_map_intent_flags_append_and_clearing_warns_only_when_it_drops_intent(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    created = runner.invoke(init, ["proj", "--dir", str(tmp_path), "--no-prompt"])
    assert created.exit_code == 0, created.output
    project_yaml = tmp_path / "proj" / ".biotope" / "project.yaml"
    monkeypatch.chdir(tmp_path / "proj")

    silent = runner.invoke(map_group, ["--clear-entities", "--entity", "gene"])
    assert silent.exit_code == 0, silent.output
    assert "Destructive" not in silent.output

    appended = runner.invoke(map_group, ["--entity", "drug_target", "--relation", "drug_targets_gene"])
    assert appended.exit_code == 0, appended.output
    intent = yaml.safe_load(project_yaml.read_text())
    assert intent["required_entities"] == ["gene", "drug_target"]
    assert intent["required_relations"] == ["drug_targets_gene"]

    entities = runner.invoke(map_group, ["--clear-entities", "--entity", "compound"])
    assert entities.exit_code == 0, entities.output
    assert "Destructive" in entities.output
    assert "required_entities" in entities.output
    assert "gene" in entities.output and "drug_target" in entities.output
    assert "required_relations" not in entities.output

    relations = runner.invoke(map_group, ["--clear-relations"])
    assert relations.exit_code == 0, relations.output
    assert "Destructive" in relations.output
    assert "required_relations" in relations.output and "drug_targets_gene" in relations.output
    intent = yaml.safe_load(project_yaml.read_text())
    assert intent["required_entities"] == ["compound"]
    assert intent["required_relations"] == []


def test_map_reads_and_writes_only_the_project_yaml_in_biotope(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    assert runner.invoke(init, [".", "--dir", str(tmp_path), "--no-prompt"]).exit_code == 0
    host = tmp_path / "src/project.yaml"
    host.parent.mkdir()
    host.write_text("name: host-tool\npurpose: Not biotope's.\n")
    monkeypatch.chdir(host.parent)

    result = runner.invoke(map_group, ["--purpose", "Who works on what"])

    assert result.exit_code == 0, result.output
    assert host.read_text() == "name: host-tool\npurpose: Not biotope's.\n"
    assert yaml.safe_load((tmp_path / ".biotope/project.yaml").read_text())["purpose"] == "Who works on what"
