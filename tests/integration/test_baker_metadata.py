"""Real baker contracts with small independently defined structures."""

import gzip
import json

import h5py
import numpy as np
import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
import tifffile
from PIL import Image

from biotope.commands.add import _add_file, _bake_directory
from biotope.commands.map_wizard import _pick_record_set
from biotope.croissant.mapping import Mapping, inspect_dataset, preview_mapping
from biotope.croissant.spec import load_from_path


def _workbook(path, column="gene_id"):
    book = openpyxl.Workbook()
    book.active.title = "Measurements"
    book.active.append([column, "score"])
    book.active.append(["G1", 1.5])
    sheet = book.create_sheet("Study")
    sheet.append(["study_id", "species"])
    sheet.append(["S1", "human"])
    book.save(path)


def test_single_workbook_uses_full_assembly_and_only_selected_file(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    workbook = raw / "study[1].xlsx"
    _workbook(workbook)
    (raw / "nested").mkdir()
    _workbook(raw / "nested" / workbook.name, "unselected")
    metadata_dir = tmp_path / ".biotope" / "datasets"
    assert _add_file(workbook, tmp_path, metadata_dir, False)
    manifest = metadata_dir / "raw" / "study[1].jsonld"
    data = json.loads(manifest.read_text())
    assert {rs["name"] for rs in data["recordSet"]} == {"Measurements", "Study"}
    assert {f["name"] for rs in data["recordSet"] for f in rs["field"]} == {"gene_id", "score", "study_id", "species"}
    objects = [d for d in data["distribution"] if d["@type"] == "cr:FileObject"]
    assert len(objects) == 1
    assert objects[0]["contentUrl"] == "raw/study[1].xlsx"
    assert all(f["source"]["fileObject"]["@id"] == objects[0]["@id"] for rs in data["recordSet"] for f in rs["field"])


def test_directory_workbook_ids_disambiguate_mapping_and_wizard(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    _workbook(raw / "a.xlsx", "a_id")
    _workbook(raw / "b.xlsx", "b_id")
    _bake_directory(raw, tmp_path)
    dataset = load_from_path(tmp_path / ".biotope" / "datasets" / "raw.jsonld")
    repeated = [rs for rs in dataset.record_set if rs.name == "Measurements"]
    assert len(repeated) == 2
    assert len({rs.id for rs in repeated}) == 2
    inspection = inspect_dataset(dataset)
    for record_set in repeated:
        selected = inspection.by_name(record_set.id)
        assert selected is not None
        assert selected.id == record_set.id
        assert selected.source in {"a.xlsx", "b.xlsx"}
        mapping = Mapping.model_validate(
            {
                "croissant": "metadata.jsonld",
                "entities": {
                    "gene": {"record_set": record_set.id, "id": record_set.field[0].name},
                },
            }
        )
        assert preview_mapping(mapping, dataset).findings == []
    ambiguous = Mapping.model_validate(
        {
            "croissant": "metadata.jsonld",
            "entities": {
                "gene": {"record_set": "Measurements", "id": "a_id"},
            },
        }
    )
    assert any("ambiguous" in f.message and f.severity == "error" for f in preview_mapping(ambiguous, dataset).findings)
    monkeypatch.setattr("biotope.commands.map_wizard.IntPrompt.ask", lambda *a, **k: 2)
    assert _pick_record_set(inspection, None) == inspection.record_sets[1].id


def test_directory_formats_and_coverage_diagnostics(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "table.csv.gz").write_bytes(gzip.compress(b"gene_id,score\nG1,2.5\n"))
    (raw / "family.soft").write_text(
        "^SAMPLE = GSM1\n!Sample_title = example\n!sample_table_begin\nID_REF\tVALUE\nG1\t2.5\n"
    )
    with h5py.File(raw / "matrix.h5", "w") as container:
        container.create_dataset("expression", shape=(2, 3), dtype="float32")
    Image.new("RGB", (4, 3)).save(raw / "image.png")
    (raw / "bad.soft").write_text("not GEO")
    (raw / "archive.zarr.zip").write_bytes(b"unsupported fixture")
    result, count = _bake_directory(raw, tmp_path)
    assert count == 6
    fields = [f for rs in result["recordSet"] for f in rs["field"]]
    assert {"gene_id", "score", "expression", "title"} <= {f["name"] for f in fields}
    matrix = next(f for f in fields if f["name"] == "expression")
    assert matrix["cr:arrayShape"] == "2,3"
    inspected = inspect_dataset(load_from_path(tmp_path / ".biotope" / "datasets" / "raw.jsonld"))
    assert inspected.by_name("matrix").to_json()["fields"][0]["array_shape"] == "2,3"
    assert any("Partial parse" in rs["description"] for rs in result["recordSet"])
    objects = [d for d in result["distribution"] if d["@type"] == "cr:FileObject"]
    assert len(objects) == 6
    assert next(d for d in objects if d["name"] == "table.csv.gz")["encodingFormat"] == ["text/csv", "application/gzip"]
    output = capsys.readouterr().out
    assert "Scanned 6 file(s): 4 described, 2 not described." in output
    assert "bad.soft" in output and "extraction failed" in output
    assert "archive.zarr.zip" in output and "archive" in output
    assert "Partial parse" in output
    assert "completeness" in output.lower()


def test_nested_parquet_json_and_single_ome_preserve_baker_structure(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    pq.write_table(
        pa.table({"gene_id": ["G1"], "annotations": [[{"term": "T1", "score": 1.5}]]}), raw / "genes.parquet"
    )
    (raw / "study.json").write_text('[{"study_id": "S1", "species": "human"}]')
    data, _ = _bake_directory(raw, tmp_path)
    nested = next(f for rs in data["recordSet"] for f in rs["field"] if f["name"] == "annotations")
    assert nested["cr:isArray"] is True
    assert {f["name"] for f in nested["subField"]} == {"term", "score"}
    assert "study_id" in {f["name"] for rs in data["recordSet"] for f in rs["field"]}
    ome = raw / "cells.ome.tif"
    tifffile.imwrite(ome, np.zeros((3, 4), dtype=np.uint8), ome=True, metadata={"axes": "YX"})
    assert _add_file(ome, tmp_path, tmp_path / ".biotope" / "datasets", False)
    single = json.loads((tmp_path / ".biotope" / "datasets" / "raw" / "cells.ome.jsonld").read_text())
    assert any(rs["name"] == "ome_images" for rs in single["recordSet"])
    assert "4x3" in single["recordSet"][0]["description"]
    assert "pixel_type" in {f["name"] for rs in single["recordSet"] for f in rs["field"]}


def test_unnamed_csv_column_uses_declared_id_without_rejecting_dataset(tmp_path):
    source = tmp_path / "indexed.csv"
    source.write_text(",gene_id,score\n0,G1,2.5\n")
    manifest_dir = tmp_path / ".biotope" / "datasets"
    assert _add_file(source, tmp_path, manifest_dir, False)
    manifest = manifest_dir / "indexed.jsonld"
    raw = json.loads(manifest.read_text())
    unnamed = raw["recordSet"][0]["field"][0]
    assert "name" not in unnamed
    assert unnamed["@id"] == "indexed/"
    source.unlink()  # All remaining work must use the description alone.
    dataset = load_from_path(manifest)
    inspection = inspect_dataset(dataset)
    assert {f.name for f in inspection.record_sets[0].fields} == {"indexed/", "gene_id", "score"}
    mapping = Mapping.model_validate(
        {
            "croissant": str(manifest),
            "entities": {"gene": {"record_set": "indexed", "id": "gene_id", "properties": {"score": "score"}}},
        }
    )
    checked = preview_mapping(mapping, dataset)
    assert checked.findings == []
    assert checked.unresolved_slots == []
    assert checked.entities[0].properties["score"] == "float"
