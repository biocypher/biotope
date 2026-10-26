import json
from pathlib import Path

import croissant_baker.scan
import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from click.testing import CliRunner
from croissant_baker.metadata_generator import MetadataGenerator

from biotope.cli import cli


DECOMPOSED = "Résumé notes.pdf"
COMPOSED_ID = "docs/Résumé%20notes.pdf"


def invoke(*args):
    return CliRunner().invoke(cli, list(args))


def tables_and_documents(root: Path) -> None:
    for folder in ("sub", "push", "docs", "events"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    (root / "people.csv").write_text("id,name\n1,Ada\n2,Grace\n")
    (root / "sub/people.csv").write_text("id,name\n3,Lin\n")
    (root / "push/records.jsonl").write_text('{"doi": "10.1/x", "year": 2024}\n')
    book = openpyxl.Workbook()
    people = book.active
    assert people is not None
    people.title = "People"
    people.append(["id", "name"])
    people.append([1, "Ada"])
    samples = book.create_sheet("Samples")
    samples.append(["sample", "score"])
    samples.append(["s1", 1.5])
    book.save(root / "book.xlsx")
    for part in (0, 1):
        pq.write_table(pa.table({"k": [part], "v": [str(part)]}), root / f"events/part-{part}.parquet")
    (root / "docs" / DECOMPOSED).write_bytes(b"%PDF-1.4 notes")
    (root / "docs/page.html").write_text("<html><body>CHC</body></html>")


def listed(monkeypatch, order):
    discover = croissant_baker.scan.discover_files
    monkeypatch.setattr(croissant_baker.scan, "discover_files", lambda *a, **k: order(discover(*a, **k)))


def baked(monkeypatch, project: Path, folder: str, single: str) -> tuple[dict, dict]:
    tables_and_documents(project / folder)
    (project / single).parent.mkdir(parents=True)
    (project / single).write_text('{"doi": "10.1/y", "year": 2025}\n')
    monkeypatch.chdir(project)
    result = invoke("init", ".", "--no-prompt")
    assert result.exit_code == 0, result.output
    result = invoke("add", folder, single)
    assert result.exit_code == 0, result.output
    datasets = project / ".biotope/datasets"
    return (
        json.loads((datasets / f"{folder}.jsonld").read_text()),
        json.loads((datasets / Path(single).with_suffix(".jsonld")).read_text()),
    )


def identities(metadata: dict) -> list[str]:
    found: list[str] = []

    def visit(node: object) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("@id"), str):
                found.append(node["@id"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit([metadata.get("distribution"), metadata.get("recordSet")])
    return sorted(found)


def test_ids_are_paths_in_the_dataset_wherever_it_sits_and_however_files_are_listed(tmp_path, monkeypatch):
    listed(monkeypatch, sorted)
    folder, single = baked(monkeypatch, tmp_path / "one", "data/study", "data/push/records.jsonl")
    listed(monkeypatch, lambda files: sorted(files, reverse=True))
    moved_folder, moved_single = baked(
        monkeypatch, tmp_path / "two", "archive/2024/study", "raw/2024/push/records.jsonl"
    )

    assert identities(moved_folder) == identities(folder)
    assert identities(moved_single) == identities(single)
    files = {entry["@id"] for entry in folder["distribution"]}
    assert files == {
        "people.csv",
        "sub/people.csv",
        "push/records.jsonl",
        "book.xlsx",
        "events/part-0.parquet",
        "events/part-1.parquet",
        "events%20partition%20files",
        COMPOSED_ID,
        "docs/page.html",
    }
    tables = {record["@id"]: record for record in folder["recordSet"]}
    assert set(tables) == {
        "people.csv#people",
        "sub/people.csv#people",
        "push/records.jsonl#records",
        "book.xlsx#People",
        "book.xlsx#Samples",
        "events%20partition%20files#events",
    }
    for identity, record in tables.items():
        for field in record["field"]:
            assert field["@id"].startswith(identity + "/")
            source = field["source"].get("fileObject") or field["source"].get("fileSet")
            assert source["@id"] in files
    assert {field["@id"] for field in tables["people.csv#people"]["field"]} == {
        "people.csv#people/id",
        "people.csv#people/name",
    }
    [table] = single["recordSet"]
    assert [entry["@id"] for entry in single["distribution"]] == ["records.jsonl"]
    assert table["@id"] == "records.jsonl#records"


class CaseTwins(MetadataGenerator):
    def generate_metadata(self, progress_callback=None):
        metadata = super().generate_metadata(progress_callback)
        [people] = [entry for entry in metadata["distribution"] if entry.get("contentUrl") == "People.csv"]
        metadata["distribution"].append({**people, "@id": "file_9", "contentUrl": "people.csv"})
        return metadata


@pytest.mark.parametrize("kind", ["case", "file set"])
def test_paths_differing_only_in_case_and_a_file_set_name_used_twice_fail_naming_them(tmp_path, monkeypatch, kind):
    monkeypatch.chdir(tmp_path)
    assert invoke("init", ".", "--no-prompt").exit_code == 0
    dataset = tmp_path / "data/study"
    if kind == "case":
        dataset.mkdir(parents=True)
        (dataset / "People.csv").write_text("id,name\n1,Ada\n")
        monkeypatch.setattr("croissant_baker.metadata_generator.MetadataGenerator", CaseTwins)
        named = ("People.csv", "people.csv")
    else:
        for folder in ("a/sales", "b/sales"):
            (dataset / folder).mkdir(parents=True)
            for part in (0, 1):
                table = pa.table({"k": [part], "v": [folder]})
                pq.write_table(table, dataset / folder / f"part-{part}.parquet")
        named = ("sales partition files", "a/sales/*.parquet", "b/sales/*.parquet")

    result = invoke("add", "data/study")

    assert result.exit_code != 0
    message = " ".join(result.output.split())
    assert all(name in message for name in named), message
    assert not (tmp_path / ".biotope/datasets/data/study.jsonld").exists()
