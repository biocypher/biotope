"""Tests for `biotope describe`."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from biotope.commands.describe import describe
from biotope.commands.init import init
from biotope.project_model import Project


def _init(runner: CliRunner, tmp_path: Path, name: str = "p") -> Path:
    result = runner.invoke(init, [name, "--dir", str(tmp_path), "--no-git"])
    assert result.exit_code == 0, result.output
    return tmp_path / name


def test_describe_records_flags(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _init(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    result = runner.invoke(
        describe,
        [
            "--purpose",
            "T2D drug-target",
            "--entity",
            "gene",
            "--entity",
            "disease",
            "--relation",
            "gene_associated_with_disease",
        ],
    )
    assert result.exit_code == 0, result.output

    project = Project.load(project_dir / ".biotope" / "project.yaml")
    assert project.purpose == "T2D drug-target"
    assert project.required_entities == ["gene", "disease"]
    assert project.required_relations == ["gene_associated_with_disease"]


def test_describe_clear_resets_lists(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _init(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    runner.invoke(describe, ["--entity", "old1", "--entity", "old2"])
    result = runner.invoke(describe, ["--clear-entities", "--entity", "new1"])
    assert result.exit_code == 0, result.output

    project = Project.load(project_dir / ".biotope" / "project.yaml")
    assert project.required_entities == ["new1"]


def test_describe_show(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _init(runner, tmp_path, name="show-test")
    monkeypatch.chdir(project_dir)

    runner.invoke(describe, ["--purpose", "hello"])
    result = runner.invoke(describe, ["--show"])
    assert result.exit_code == 0
    assert "hello" in result.output


def test_describe_fails_without_project(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(describe, ["--purpose", "x"])
    assert result.exit_code != 0
    assert "No project.yaml found" in result.output
