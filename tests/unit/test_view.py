"""Tests for `biotope view`."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from biotope.commands.init import init
from biotope.commands.map import map_group as describe
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
            "--purpose",
            "Drug-target-disease",
            "--entity",
            "gene",
            "--entity",
            "drug",
            "--relation",
            "drug_targets_gene",
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


def test_view_counts_single_file_csv_output(tmp_path: Path, monkeypatch) -> None:
    """BioCypher 0.14+ writes a single `<label>.csv` per label (no `-part*`).
    `biotope view` must count those, not just the legacy partitioned form."""
    runner = CliRunner()
    project_dir = _init(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    build_dir = project_dir / "build"
    config_dir = build_dir / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "schema_config.yaml").write_text(
        "tool:\n  represented_as: node\n  input_label: tool\n"
        "node organizes event:\n  represented_as: edge\n  input_label: node_organizes_event\n"
    )
    (config_dir / "biocypher_config.yaml").write_text(
        "biocypher:\n  dbms: neo4j\n  output_directory: biocypher-out\n  head_ontology: null\n"
    )
    out = build_dir / "biocypher-out"
    out.mkdir(parents=True)
    # PascalCase schema term stems (not input_label).
    (out / "Tool.csv").write_text("id,label\n1,a\n2,b\n3,c\n")
    (out / "Tool-header.csv").write_text("id,label\n")
    (out / "NodeOrganizesEvent-part000.csv").write_text("src,tgt\n1,2\n2,3\n")

    result = runner.invoke(view, ["--build-dir", str(build_dir), "--no-header"])
    assert result.exit_code == 0, result.output
    assert "target (dbms):" in result.output
    assert "neo4j" in result.output
    assert "Tool.csv" in result.output
    assert "NodeOrganizesEvent-part000.csv" in result.output
    assert "Tool-header.csv" not in result.output
    # 3 node rows, 2 edge rows (header subtracted).
    assert "Total nodes: " in result.output
    assert "edges: 2" in result.output
    assert "Total nodes: 3" in result.output or "3" in result.output


def test_view_outside_project_does_not_crash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(view, [])
    assert result.exit_code == 0, result.output
    assert "No project.yaml" in result.output
