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

from biotope.commands.add import _bake_directory, add_file
from biotope.croissant.inspector import inspect_dataset
from biotope.croissant.spec import load_from_path
from biotope.graph.inventory import generate_source_packages


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
    assert add_file(workbook, tmp_path, metadata_dir, False)
    manifest = metadata_dir / "raw" / "study[1].xlsx.jsonld"
    data = json.loads(manifest.read_text())
    assert {rs["name"] for rs in data["recordSet"]} == {"Measurements", "Study"}
    assert {f["name"] for rs in data["recordSet"] for f in rs["field"]} == {"gene_id", "score", "study_id", "species"}
    objects = [d for d in data["distribution"] if d["@type"] == "cr:FileObject"]
    assert len(objects) == 1
    assert objects[0]["contentUrl"] == "raw/study[1].xlsx"
    assert all(f["source"]["fileObject"]["@id"] == objects[0]["@id"] for rs in data["recordSet"] for f in rs["field"])


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
    output = capsys.readouterr()
    assert output.out == ""
    assert "\x1b" not in output.err
    text = "\n".join(line.rstrip() for line in output.err.splitlines())
    assert "6 scanned · 4 described · 2 not described" in text
    assert "bad.soft" in text and "Extraction failed" in text
    assert "SKIP   archive.zarr.zip\n       Archive; the baker does not open archives" in text
    assert "OK     table.csv.gz" in text
    assert "parsed as far as it goes" in text


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
    assert add_file(ome, tmp_path, tmp_path / ".biotope" / "datasets", False)
    single = json.loads((tmp_path / ".biotope" / "datasets" / "raw" / "cells.ome.tif.jsonld").read_text())
    assert any(rs["name"] == "ome_images" for rs in single["recordSet"])
    assert "4x3" in single["recordSet"][0]["description"]
    assert "pixel_type" in {f["name"] for rs in single["recordSet"] for f in rs["field"]}


def test_unnamed_csv_column_uses_declared_id_without_rejecting_dataset(tmp_path):
    source = tmp_path / "indexed.csv"
    source.write_text(",gene_id,score\n0,G1,2.5\n")
    manifest_dir = tmp_path / ".biotope" / "datasets"
    assert add_file(source, tmp_path, manifest_dir, False)
    manifest = manifest_dir / "indexed.csv.jsonld"
    raw = json.loads(manifest.read_text())
    unnamed = raw["recordSet"][0]["field"][0]
    assert "name" not in unnamed
    assert unnamed["@id"] == "indexed.csv#indexed/"
    source.unlink()
    dataset = load_from_path(manifest)
    inspection = inspect_dataset(dataset)
    assert {f.name for f in inspection.record_sets[0].fields} == {"indexed.csv#indexed/", "gene_id", "score"}
    generate_source_packages(manifest, tmp_path / "sources")
    assert "indexed.csv#indexed/" in (tmp_path / "sources/indexed_csv/indexed_csv_indexed/schema.py").read_text()
