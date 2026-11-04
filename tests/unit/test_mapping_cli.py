from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from biotope.commands.init import init
from biotope.commands.map import map_group


def test_project_yaml_holds_one_purpose_and_refuses_any_other_key(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    created = runner.invoke(init, ["proj", "--dir", str(tmp_path), "--no-prompt"])
    assert created.exit_code == 0, created.output
    project_yaml = tmp_path / "proj" / ".biotope" / "project.yaml"
    monkeypatch.chdir(tmp_path / "proj")

    purpose = "Grant officers ask which researchers work on a topic and how often they publish."
    recorded = runner.invoke(map_group, ["--purpose", purpose])
    assert recorded.exit_code == 0, recorded.output
    assert yaml.safe_load(project_yaml.read_text()) == {"purpose": purpose}
    assert purpose in " ".join(runner.invoke(map_group, ["--show"]).output.split())

    project_yaml.write_text(f"purpose: {purpose}\nrequired_entities: [researcher]\n")
    refused = runner.invoke(map_group, ["--show"])
    assert refused.exit_code != 0
    assert "required_entities" in refused.output


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
