"""Tests for `biotope rm`."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from click.testing import CliRunner

from biotope.commands.init import init
from biotope.commands.rm import rm


def _project(runner: CliRunner, tmp_path: Path) -> Path:
    r = runner.invoke(init, ["proj", "--dir", str(tmp_path), "--no-prompt"])
    assert r.exit_code == 0, r.output
    project_dir = tmp_path / "proj"
    return project_dir


def _write_manifest(
    project_dir: Path,
    rel_id: str,
    distribution: list[dict] | None = None,
    status: str = "raw",
) -> Path:
    manifest_path = project_dir / ".biotope" / "datasets" / f"{rel_id}.jsonld"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "@type": "sc:Dataset",
                "name": rel_id,
                "distribution": distribution or [],
                "biotope:status": status,
            }
        )
    )
    return manifest_path


# ---------------------------------------------------------------------------
# Whole-dataset removal
# ---------------------------------------------------------------------------


def test_rm_whole_dataset_deletes_data_and_manifest(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    data_dir = project_dir / "data" / "ot" / "target"
    data_dir.mkdir(parents=True)
    (data_dir / "part-00.parquet").write_bytes(b"x")
    _write_manifest(project_dir, "data/ot/target")

    r = runner.invoke(rm, [str(data_dir), "--force"])
    assert r.exit_code == 0, r.output

    assert not data_dir.exists()
    assert not (project_dir / ".biotope" / "datasets" / "data" / "ot" / "target.jsonld").exists()


def test_rm_whole_dataset_keep_data(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    data_dir = project_dir / "data" / "ot" / "target"
    data_dir.mkdir(parents=True)
    (data_dir / "x.parquet").write_bytes(b"x")
    _write_manifest(project_dir, "data/ot/target")

    r = runner.invoke(rm, [str(data_dir), "--force", "--keep-data"])
    assert r.exit_code == 0, r.output
    assert data_dir.exists()
    assert not (project_dir / ".biotope" / "datasets" / "data" / "ot" / "target.jsonld").exists()


def test_rm_canonical_id_accepted_when_data_already_gone(tmp_path: Path, monkeypatch) -> None:
    """User may have already deleted the data dir; `biotope rm <canonical_id>`
    still cleans up the orphaned manifest."""
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)
    _write_manifest(project_dir, "data/ot/orphan")

    r = runner.invoke(rm, ["data/ot/orphan", "--force"])
    assert r.exit_code == 0, r.output
    assert not (project_dir / ".biotope" / "datasets" / "data" / "ot" / "orphan.jsonld").exists()


def test_rm_directory_without_manifest_refuses(tmp_path: Path, monkeypatch) -> None:
    """A directory that isn't a tracked dataset shouldn't be silently nuked."""
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    untracked = project_dir / "data" / "wat"
    untracked.mkdir(parents=True)

    r = runner.invoke(rm, [str(untracked), "--force"])
    assert r.exit_code != 0
    assert "not a tracked dataset" in r.output


# ---------------------------------------------------------------------------
# Single-file removal in a multi-file manifest
# ---------------------------------------------------------------------------


def test_rm_single_file_object_keeps_other_distribution_entries(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    data_dir = project_dir / "data" / "ot"
    data_dir.mkdir(parents=True)
    target = data_dir / "README.md"
    target.write_text("notes")
    other = data_dir / "CHANGELOG.md"
    other.write_text("changes")

    _write_manifest(
        project_dir,
        "data/ot",
        distribution=[
            {"@type": "cr:FileObject", "@id": "f1", "contentUrl": "data/ot/README.md"},
            {"@type": "cr:FileObject", "@id": "f2", "contentUrl": "data/ot/CHANGELOG.md"},
        ],
    )

    r = runner.invoke(rm, [str(target), "--force"])
    assert r.exit_code == 0, r.output

    assert not target.exists()
    assert other.exists()  # untouched
    manifest = project_dir / ".biotope" / "datasets" / "data" / "ot.jsonld"
    assert manifest.exists()
    metadata = json.loads(manifest.read_text())
    urls = [d["contentUrl"] for d in metadata["distribution"]]
    assert urls == ["data/ot/CHANGELOG.md"]


def test_rm_last_file_in_manifest_deletes_manifest(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    data_dir = project_dir / "data" / "lone"
    data_dir.mkdir(parents=True)
    target = data_dir / "only.csv"
    target.write_text("a,b\n1,2\n")

    _write_manifest(
        project_dir,
        "data/lone",
        distribution=[
            {"@type": "cr:FileObject", "@id": "f1", "contentUrl": "data/lone/only.csv"},
        ],
    )

    r = runner.invoke(rm, [str(target), "--force"])
    assert r.exit_code == 0, r.output

    manifest = project_dir / ".biotope" / "datasets" / "data" / "lone.jsonld"
    assert not manifest.exists()
    assert "manifest" in r.output and "empty" in r.output


def test_rm_fileset_covered_file_refuses(tmp_path: Path, monkeypatch) -> None:
    """Removing one FileSet-covered file would leave the glob stale; refuse."""
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    data_dir = project_dir / "data" / "ot" / "target"
    data_dir.mkdir(parents=True)
    target = data_dir / "part-00.parquet"
    target.write_bytes(b"x")

    _write_manifest(
        project_dir,
        "data/ot/target",
        distribution=[{"@type": "cr:FileSet", "@id": "fs", "includes": "*.parquet"}],
    )

    r = runner.invoke(rm, [str(target), "--force"])
    assert r.exit_code != 0
    assert "FileSet" in r.output
    assert target.exists()  # nothing deleted


def test_rm_keep_data_for_file(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    data_dir = project_dir / "data" / "ot"
    data_dir.mkdir(parents=True)
    target = data_dir / "README.md"
    target.write_text("notes")

    _write_manifest(
        project_dir,
        "data/ot",
        distribution=[
            {"@type": "cr:FileObject", "@id": "f1", "contentUrl": "data/ot/README.md"},
            {"@type": "cr:FileObject", "@id": "f2", "contentUrl": "data/ot/other.md"},
        ],
    )

    r = runner.invoke(rm, [str(target), "--force", "--keep-data"])
    assert r.exit_code == 0, r.output
    assert target.exists()  # disk untouched
    metadata = json.loads((project_dir / ".biotope" / "datasets" / "data" / "ot.jsonld").read_text())
    assert all(d["contentUrl"] != "data/ot/README.md" for d in metadata["distribution"])


def test_rm_accepts_a_file_baker_described_in_a_folder_manifest(tmp_path: Path, monkeypatch) -> None:
    from biotope.cli import cli

    runner = CliRunner()
    assert runner.invoke(cli, ["init", "baked", "--dir", str(tmp_path), "--no-prompt"]).exit_code == 0
    root = tmp_path / "baked"
    monkeypatch.chdir(root)
    things = root / "data/things"
    shutil.copytree(Path(__file__).resolve().parents[1] / "fixtures/things", things)
    assert runner.invoke(cli, ["add", "data/things"]).exit_code == 0
    removed = runner.invoke(cli, ["rm", "-f", "data/things/second.csv"])
    assert removed.exit_code == 0, removed.output
    assert not (things / "second.csv").exists()
    manifest = json.loads((root / ".biotope/datasets/data/things.jsonld").read_text())
    assert [entry["contentUrl"] for entry in manifest["distribution"]] == ["first.csv"]
    [kept] = manifest["recordSet"]
    assert {field["name"] for field in kept["field"]} == {"a", "b"}
