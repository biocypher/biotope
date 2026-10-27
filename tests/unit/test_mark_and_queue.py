from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from biotope.commands.init import init
from biotope.commands.mark import mark
from biotope.commands.queue import queue


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> Path:
    created = CliRunner().invoke(init, ["proj", "--dir", str(tmp_path), "--no-prompt"])
    assert created.exit_code == 0, created.output
    monkeypatch.chdir(tmp_path / "proj")
    return tmp_path / "proj"


def _write_manifest(
    project_dir: Path,
    rel_id: str,
    *,
    status: str = "raw",
    derived_from: list[str] | None = None,
    date_created: str | None = None,
) -> Path:
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


def test_mark_sets_status_and_lineage_and_refuses_an_unknown_dataset(project: Path) -> None:
    runner = CliRunner()
    target = "data/ot/target with spaces [dim] and brackets"
    _write_manifest(project, target, status="processed")
    _write_manifest(project, "raw_pdf", status="raw")

    marked = runner.invoke(mark, [target, "mapped", "--derived-from", "raw_pdf"])
    assert marked.exit_code == 0, marked.output
    assert target in marked.output and "raw_pdf" in marked.output
    metadata = json.loads((project / ".biotope" / "datasets" / f"{target}.jsonld").read_text())
    assert metadata["biotope:status"] == "mapped"
    assert metadata["prov:wasDerivedFrom"] == [{"@id": "raw_pdf"}]

    missing = runner.invoke(mark, ["ghost/dataset", "processed"])
    assert missing.exit_code != 0
    assert "no manifest found" in missing.output.lower()


def test_queue_lists_datasets_by_status_oldest_raw_first_and_flags_dangling_lineage(project: Path) -> None:
    runner = CliRunner()
    _write_manifest(project, "second", status="raw", date_created="2026-05-10T00:00:00Z")
    _write_manifest(project, "first", status="raw", date_created="2026-05-01T00:00:00Z")
    _write_manifest(project, "consumed_pdf", status="raw")
    _write_manifest(project, "structured", status="processed", derived_from=["consumed_pdf"])
    _write_manifest(project, "in_kg", status="mapped")
    _write_manifest(project, "orphan", status="processed", derived_from=["ghost"])

    shown = runner.invoke(queue, [])
    assert shown.exit_code == 0, shown.output
    raw_section = shown.output.split("PROCESSED")[0]
    assert "RAW" in raw_section and raw_section.index("first") < raw_section.index("second")
    assert "consumed_pdf" not in raw_section
    assert "PROCESSED" in shown.output and "structured" in shown.output
    assert "MAPPED" in shown.output and "in_kg" in shown.output
    assert "manually marked" in shown.output and "in the KG" not in shown.output
    assert "consumed_pdf" in shown.output.split("already consumed")[1]
    assert "ghost" in shown.output.split("ANOMALIES")[1]

    listed = runner.invoke(queue, ["--json"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    assert [entry["id"] for entry in payload["sections"]["raw"]] == ["first", "second"]
    processed = {entry["id"]: entry["derived_from"] for entry in payload["sections"]["processed"]}
    assert processed["structured"] == ["consumed_pdf"]
    assert [entry["id"] for entry in payload["raw_consumed"]] == ["consumed_pdf"]

    mapped = runner.invoke(queue, ["--status", "mapped"])
    assert mapped.exit_code == 0
    assert "MAPPED" in mapped.output and "in_kg" in mapped.output
    assert "RAW" not in mapped.output
