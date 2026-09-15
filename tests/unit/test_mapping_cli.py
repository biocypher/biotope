"""End-to-end CLI walkthrough on the semantic IR: init -> intent -> mapping scaffolds."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from biotope.commands.init import init
from biotope.commands.map import map_group


FIXTURES = Path(__file__).parent.parent / "fixtures" / "croissant"


def test_map_intent_flags_update_project(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    r = runner.invoke(init, ["bcc-e2e", "--dir", str(tmp_path), "--no-git", "--no-prompt"])
    assert r.exit_code == 0, r.output
    project_dir = tmp_path / "bcc-e2e"
    monkeypatch.chdir(project_dir)

    r = runner.invoke(map_group, ["--entity", "gene", "--relation", "gene_in_disease"])
    assert r.exit_code == 0, r.output
    project_yaml = yaml.safe_load((project_dir / ".biotope" / "project.yaml").read_text())
    assert project_yaml["required_entities"] == ["gene"]
    assert project_yaml["required_relations"] == ["gene_in_disease"]
