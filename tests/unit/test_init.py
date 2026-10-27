"""Tests for the scaffold-only `biotope init`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from biotope.cli import cli
from biotope.commands.init import init
from biotope.project_model import Project


def _invoke(runner: CliRunner, *args: str) -> object:
    return runner.invoke(init, list(args))


def test_init_default_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner(mix_stderr=False)
    monkeypatch.chdir(tmp_path)
    outside = runner.invoke(cli, ["status"])
    assert outside.exit_code != 0
    assert "Not in a biotope project" in outside.stderr

    result = _invoke(runner, "myproj", "--dir", str(tmp_path))
    assert result.exit_code == 0, result.output

    assert "biotope add" in result.output
    root = tmp_path / "myproj"
    monkeypatch.chdir(root)
    status = runner.invoke(cli, ["status"])
    assert status.exit_code == 0, status.output
    assert "No datasets" in status.output
    check = runner.invoke(cli, ["check-data"])
    assert check.exit_code == 0, check.output
    assert "No files to check." in check.output
    queue = runner.invoke(cli, ["queue", "--json"])
    assert queue.exit_code == 0, queue.output
    assert json.loads(queue.output)["sections"] == {"raw": [], "processed": [], "mapped": []}
    for directory in ("data", "mappings", "graph", ".biotope/datasets", ".biotope/workflows"):
        assert not (root / directory).exists()
    assert (root / ".biotope" / "config.yaml").is_file()
    assert (root / ".biotope" / "project.yaml").is_file()
    assert (root / ".gitignore").is_file()
    assert not (root / "pyproject.toml").exists()
    config = yaml.safe_load((root / ".biotope" / "config.yaml").read_text())
    assert config["croissant_schema_version"] == "1.1"
    assert config["annotation_validation"]["enabled"] is True
    assert {"creator", "distribution"} <= set(config["annotation_validation"]["minimum_required_fields"])
    assert config["annotation_validation"]["field_validation"]["description"]["min_length"] == 10


def test_init_purpose_flag_is_recorded(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _invoke(
        runner,
        "p",
        "--dir",
        str(tmp_path),
        "--purpose",
        "Map drug-target-disease links for type-2 diabetes",
    )
    assert result.exit_code == 0, result.output

    project = Project.load(tmp_path / "p" / ".biotope" / "project.yaml")
    assert "type-2 diabetes" in project.purpose


def test_init_refuses_existing_biotope(tmp_path: Path) -> None:
    runner = CliRunner()
    first = _invoke(runner, "twice", "--dir", str(tmp_path))
    assert first.exit_code == 0
    second = _invoke(runner, "twice", "--dir", str(tmp_path))
    assert second.exit_code != 0
    assert "already contains" in second.output
