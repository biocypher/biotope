"""Tests for the scaffold-only `biotope init`."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from biotope.commands.init import init
from biotope.project_model import Project


def _invoke(runner: CliRunner, *args: str) -> object:
    return runner.invoke(init, list(args))


def test_init_default_layout(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _invoke(runner, "myproj", "--dir", str(tmp_path), "--no-git")
    assert result.exit_code == 0, result.output

    root = tmp_path / "myproj"
    assert (root / ".biotope" / "datasets").is_dir()
    assert (root / ".biotope" / "workflows").is_dir()
    assert (root / "data" / "raw").is_dir()
    assert (root / "data" / "processed").is_dir()
    assert (root / "mappings").is_dir()
    assert (root / ".biotope" / "config.yaml").is_file()
    assert (root / ".biotope" / "project.yaml").is_file()
    assert (root / "AGENTS.md").is_file()
    assert (root / ".gitignore").is_file()


def test_init_purpose_flag_is_recorded(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _invoke(
        runner,
        "p",
        "--dir",
        str(tmp_path),
        "--no-git",
        "--purpose",
        "Map drug-target-disease links for type-2 diabetes",
    )
    assert result.exit_code == 0, result.output

    project = Project.load(tmp_path / "p" / ".biotope" / "project.yaml")
    assert "type-2 diabetes" in project.purpose


def test_init_visible_promotes_project_yaml(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _invoke(runner, "v", "--dir", str(tmp_path), "--no-git", "--visible")
    assert result.exit_code == 0, result.output

    root = tmp_path / "v"
    assert (root / "project.yaml").is_file()
    assert not (root / ".biotope" / "project.yaml").exists()


def test_init_refuses_existing_biotope(tmp_path: Path) -> None:
    runner = CliRunner()
    first = _invoke(runner, "twice", "--dir", str(tmp_path), "--no-git")
    assert first.exit_code == 0
    second = _invoke(runner, "twice", "--dir", str(tmp_path), "--no-git")
    assert second.exit_code != 0
    assert "already contains" in second.output


def test_init_creates_default_biotope_config(tmp_path: Path) -> None:
    runner = CliRunner()
    _invoke(runner, "c", "--dir", str(tmp_path), "--no-git")
    config = yaml.safe_load((tmp_path / "c" / ".biotope" / "config.yaml").read_text())
    assert config["croissant_schema_version"] == "1.1"
    assert config["annotation_validation"]["enabled"] is True
    assert "creator" in config["annotation_validation"]["minimum_required_fields"]
    assert "distribution" in config["annotation_validation"]["minimum_required_fields"]
    assert config["annotation_validation"]["field_validation"]["description"]["min_length"] == 10
