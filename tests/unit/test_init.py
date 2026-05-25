"""Tests for the scaffold-only `biotope init`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
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
    assert (root / "data").is_dir()
    assert (root / "mappings").is_dir()
    assert (root / ".biotope" / "config.yaml").is_file()
    assert (root / ".biotope" / "project.yaml").is_file()
    assert (root / "AGENTS.md").is_file()
    assert (root / ".gitignore").is_file()
    assert (root / "pyproject.toml").is_file()


def test_init_emits_pyproject_with_biotope_and_biocypher(tmp_path: Path) -> None:
    """The generated pyproject must pin biotope (floor) and biocypher>=0.14."""
    runner = CliRunner()
    result = _invoke(runner, "myproj", "--dir", str(tmp_path), "--no-git", "--no-prompt")
    assert result.exit_code == 0, result.output

    pyproject = (tmp_path / "myproj" / "pyproject.toml").read_text()
    assert 'name = "myproj"' in pyproject
    assert "biotope>=" in pyproject
    assert "biocypher>=0.14.0" in pyproject
    assert "requires-python" in pyproject


def test_emitted_pyproject_uses_hatchling_and_skips_package_discovery(
    tmp_path: Path,
) -> None:
    """Hatchling is the build backend (no setuptools flat-layout footgun on
    `data/`/`mappings/`) and the wheel target ships nothing — biotope projects
    are workspaces that declare deps, not Python distributions."""
    runner = CliRunner()
    result = _invoke(runner, "myproj", "--dir", str(tmp_path), "--no-git", "--no-prompt")
    assert result.exit_code == 0, result.output

    pyproject = (tmp_path / "myproj" / "pyproject.toml").read_text()
    assert 'build-backend = "hatchling.build"' in pyproject
    assert "[tool.hatch.build.targets.wheel]" in pyproject
    assert "bypass-selection = true" in pyproject


def test_init_does_not_overwrite_existing_pyproject(tmp_path: Path) -> None:
    """If the user already has a pyproject (init inside an existing project), keep it."""
    target = tmp_path / "myproj"
    target.mkdir()
    user_pyproject = '[project]\nname = "user-owned"\nversion = "9.9.9"\n'
    (target / "pyproject.toml").write_text(user_pyproject)

    runner = CliRunner()
    result = _invoke(runner, ".", "--dir", str(target), "--no-git", "--no-prompt")
    assert result.exit_code == 0, result.output

    assert (target / "pyproject.toml").read_text() == user_pyproject


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


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_init_creates_initial_commit_and_leaves_clean_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After init, the scaffold should be committed so `git status` is clean —
    otherwise init artefacts (config.yaml, AGENTS.md, ...) leak into the user's
    first `biotope status` and look like changes they made."""
    for var, val in (
        ("GIT_AUTHOR_NAME", "t"),
        ("GIT_AUTHOR_EMAIL", "t@t"),
        ("GIT_COMMITTER_NAME", "t"),
        ("GIT_COMMITTER_EMAIL", "t@t"),
    ):
        monkeypatch.setenv(var, val)
    runner = CliRunner()
    result = _invoke(runner, "g", "--dir", str(tmp_path), "--no-prompt")
    assert result.exit_code == 0, result.output

    root = tmp_path / "g"
    porcelain = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True)
    assert porcelain.stdout.strip() == "", f"expected clean tree, got:\n{porcelain.stdout}"

    log = subprocess.run(["git", "log", "--oneline"], cwd=root, capture_output=True, text=True, check=True)
    assert "initialize biotope project" in log.stdout


def test_init_creates_default_biotope_config(tmp_path: Path) -> None:
    runner = CliRunner()
    _invoke(runner, "c", "--dir", str(tmp_path), "--no-git")
    config = yaml.safe_load((tmp_path / "c" / ".biotope" / "config.yaml").read_text())
    assert config["croissant_schema_version"] == "1.1"
    assert config["annotation_validation"]["enabled"] is True
    assert "creator" in config["annotation_validation"]["minimum_required_fields"]
    assert "distribution" in config["annotation_validation"]["minimum_required_fields"]
    assert config["annotation_validation"]["field_validation"]["description"]["min_length"] == 10
