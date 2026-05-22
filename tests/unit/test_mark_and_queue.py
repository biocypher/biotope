"""Tests for `biotope mark` and `biotope queue`."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from biotope.commands.init import init
from biotope.commands.mark import mark
from biotope.commands.queue import queue


def _project(runner: CliRunner, tmp_path: Path) -> Path:
    r = runner.invoke(init, ["proj", "--dir", str(tmp_path), "--no-git", "--no-prompt"])
    assert r.exit_code == 0, r.output
    project_dir = tmp_path / "proj"
    # `find_biotope_root` requires .git alongside .biotope; --no-git skipped it.
    (project_dir / ".git").mkdir(exist_ok=True)
    return project_dir


def _write_manifest(
    project_dir: Path,
    rel_id: str,
    *,
    status: str = "raw",
    derived_from: list[str] | None = None,
    date_created: str | None = None,
) -> Path:
    """Write a minimal manifest at .biotope/datasets/<rel_id>.jsonld and return
    the manifest path. ``rel_id`` is the canonical id (no .jsonld suffix)."""
    manifest_path = project_dir / ".biotope" / "datasets" / f"{rel_id}.jsonld"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "@type": "sc:Dataset",
        "name": rel_id,
        "distribution": [],
        "biotope:status": status,
    }
    if derived_from:
        payload["prov:wasDerivedFrom"] = [{"@id": src} for src in derived_from]
    if date_created:
        payload["dateCreated"] = date_created
    manifest_path.write_text(json.dumps(payload, indent=2))
    return manifest_path


# ---------------------------------------------------------------------------
# mark
# ---------------------------------------------------------------------------


def test_mark_sets_status(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)
    _write_manifest(project_dir, "data/ot/target", status="processed")

    r = runner.invoke(mark, ["data/ot/target", "mapped"])
    assert r.exit_code == 0, r.output

    with open(project_dir / ".biotope" / "datasets" / "data" / "ot" / "target.jsonld") as f:
        metadata = json.load(f)
    assert metadata["biotope:status"] == "mapped"


def test_mark_with_derived_from_adds_provenance(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)
    _write_manifest(project_dir, "raw_pdf", status="raw")
    _write_manifest(project_dir, "extracted", status="processed")

    r = runner.invoke(mark, ["extracted", "processed", "--derived-from", "raw_pdf"])
    assert r.exit_code == 0, r.output

    with open(project_dir / ".biotope" / "datasets" / "extracted.jsonld") as f:
        metadata = json.load(f)
    assert metadata["prov:wasDerivedFrom"] == [{"@id": "raw_pdf"}]
    assert "raw_pdf" in r.output


def test_mark_rejects_missing_dataset(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    r = runner.invoke(mark, ["ghost/dataset", "processed"])
    assert r.exit_code != 0
    assert "no manifest found" in r.output.lower()


def test_mark_rejects_invalid_status(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)
    _write_manifest(project_dir, "ds", status="raw")

    r = runner.invoke(mark, ["ds", "garbage"])
    assert r.exit_code != 0


# ---------------------------------------------------------------------------
# queue
# ---------------------------------------------------------------------------


def test_queue_groups_by_status(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    _write_manifest(project_dir, "raw_doc", status="raw")
    _write_manifest(project_dir, "structured", status="processed")
    _write_manifest(project_dir, "in_kg", status="mapped")

    r = runner.invoke(queue, [])
    assert r.exit_code == 0, r.output
    assert "RAW" in r.output and "raw_doc" in r.output
    assert "PROCESSED" in r.output and "structured" in r.output
    assert "MAPPED" in r.output and "in_kg" in r.output


def test_queue_hides_consumed_raw_from_active_section(tmp_path: Path, monkeypatch) -> None:
    """A raw input that something else derivesFrom shouldn't appear as
    actionable in the agent queue — it's been consumed already."""
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    _write_manifest(project_dir, "consumed_pdf", status="raw")
    _write_manifest(project_dir, "fresh_pdf", status="raw")
    _write_manifest(project_dir, "derived", status="processed", derived_from=["consumed_pdf"])

    r = runner.invoke(queue, [])
    assert r.exit_code == 0, r.output
    # consumed_pdf appears in the "already consumed" dim section, not RAW.
    raw_section = r.output.split("PROCESSED")[0]
    assert "fresh_pdf" in raw_section
    assert "consumed_pdf" not in raw_section
    assert "already consumed" in r.output
    assert "consumed_pdf" in r.output  # shown under the consumed list


def test_queue_json_output_shape(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    _write_manifest(project_dir, "a", status="raw")
    _write_manifest(project_dir, "b", status="processed", derived_from=["a"])

    r = runner.invoke(queue, ["--json"])
    assert r.exit_code == 0, r.output
    payload = json.loads(r.output)
    assert "sections" in payload
    # "a" was consumed by "b" → not in active raw.
    assert payload["sections"]["raw"] == []
    assert len(payload["sections"]["processed"]) == 1
    assert payload["sections"]["processed"][0]["derived_from"] == ["a"]
    assert payload["raw_consumed"][0]["id"] == "a"


def test_queue_status_filter(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)
    _write_manifest(project_dir, "a", status="raw")
    _write_manifest(project_dir, "b", status="mapped")

    r = runner.invoke(queue, ["--status", "mapped"])
    assert r.exit_code == 0
    assert "MAPPED" in r.output
    assert "RAW" not in r.output
    assert "b" in r.output


def test_queue_flags_dangling_provenance(tmp_path: Path, monkeypatch) -> None:
    """If a manifest claims `wasDerivedFrom: X` but `X` no longer exists,
    surface it in the anomalies footer."""
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)
    _write_manifest(project_dir, "orphan", status="processed", derived_from=["ghost"])

    r = runner.invoke(queue, [])
    assert r.exit_code == 0, r.output
    assert "ANOMALIES" in r.output
    assert "ghost" in r.output


def test_queue_sort_time_default(tmp_path: Path, monkeypatch) -> None:
    """Default ordering puts the oldest raw first so the agent processes
    in chronological order."""
    runner = CliRunner()
    project_dir = _project(runner, tmp_path)
    monkeypatch.chdir(project_dir)

    _write_manifest(project_dir, "second", status="raw", date_created="2026-05-10T00:00:00Z")
    _write_manifest(project_dir, "first", status="raw", date_created="2026-05-01T00:00:00Z")

    r = runner.invoke(queue, [])
    assert r.exit_code == 0
    # 'first' must appear before 'second' in the RAW section.
    raw_section = r.output.split("PROCESSED")[0]
    assert raw_section.index("first") < raw_section.index("second")
