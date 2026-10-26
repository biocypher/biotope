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
    result = _invoke(runner, "myproj", "--dir", str(tmp_path))
    assert result.exit_code == 0, result.output

    assert "biotope get" not in result.output
    assert "biotope add" in result.output
    root = tmp_path / "myproj"
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


def test_init_does_not_overwrite_existing_pyproject(tmp_path: Path) -> None:
    target = tmp_path / "myproj"
    target.mkdir()
    user_pyproject = '[project]\nname = "user-owned"\nversion = "9.9.9"\n'
    (target / "pyproject.toml").write_text(user_pyproject)

    runner = CliRunner()
    result = _invoke(runner, ".", "--dir", str(target), "--no-prompt")
    assert result.exit_code == 0, result.output

    assert (target / "pyproject.toml").read_text() == user_pyproject


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
