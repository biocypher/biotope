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


def test_view_counts_single_file_csv_output(tmp_path: Path, monkeypatch) -> None:
    """BioCypher 0.14+ writes a single `<label>.csv` per label (no `-part*`).
    `biotope view` must count those, not just the legacy partitioned form."""
    runner = CliRunner()
    project_dir = _init(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    build_dir = project_dir / "build"
    out = build_dir / "biocypher-out"
    out.mkdir(parents=True)
    # Single-file form (BioCypher 0.14+) for a node label.
    (out / "Gene.csv").write_text("id,label\n1,a\n2,b\n3,c\n")
    # Header file that should be ignored.
    (out / "Gene-header.csv").write_text("id,label\n")
    # Partitioned form (older BioCypher) for an edge label, just to confirm
    # both forms count side-by-side.
    (out / "GENE_IN_DISEASE-part000.csv").write_text("src,tgt\n1,2\n2,3\n")

    result = runner.invoke(view, ["--build-dir", str(build_dir), "--no-header"])
    assert result.exit_code == 0, result.output
    assert "Gene.csv" in result.output
    assert "GENE_IN_DISEASE-part000.csv" in result.output
    assert "Gene-header.csv" not in result.output
    # 3 data rows in Gene.csv, 2 in GENE_IN_DISEASE-part000.csv (header subtracted).
    assert "Total nodes: " in result.output
    assert "3" in result.output and "2" in result.output


def test_view_outside_project_does_not_crash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(view, [])
    assert result.exit_code == 0, result.output
    assert "No project.yaml" in result.output
