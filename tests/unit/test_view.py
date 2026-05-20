"""Tests for `biotope view`."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from biotope.commands.map import map_group as describe
from biotope.commands.init import init
from biotope.commands.view import view


def _init(runner: CliRunner, tmp_path: Path) -> Path:
    r = runner.invoke(init, ["proj", "--dir", str(tmp_path), "--no-git"])
    assert r.exit_code == 0, r.output
    return tmp_path / "proj"


def test_view_surfaces_project_header_without_build(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _init(runner, tmp_path)
    monkeypatch.chdir(project_dir)
    runner.invoke(
        describe,
        [
            "--purpose", "Drug-target-disease",
            "--entity", "gene",
            "--entity", "drug",
            "--relation", "drug_targets_gene",
        ],
    )

    result = runner.invoke(view, [])
    assert result.exit_code == 0, result.output
    assert "Drug-target-disease" in result.output
    assert "gene" in result.output
    assert "drug_targets_gene" in result.output
    assert "build" in result.output.lower()


def test_view_no_header_flag(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _init(runner, tmp_path)
    monkeypatch.chdir(project_dir)
    runner.invoke(describe, ["--purpose", "PROJECT_HEADER_PURPOSE"])

    result = runner.invoke(view, ["--no-header"])
    assert result.exit_code == 0, result.output
    assert "PROJECT_HEADER_PURPOSE" not in result.output


def test_view_outside_project_does_not_crash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(view, [])
    assert result.exit_code == 0, result.output
    assert "No project.yaml" in result.output
