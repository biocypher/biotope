from pathlib import Path

import pytest

from biotope.croissant.acquisition import AcquisitionContext, RecordRow, as_curie, hash_id, passthrough
from biotope.croissant.spec import load_from_path


def test_stream_csv(minimal_croissant: Path, gene_csv: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    with AcquisitionContext(dataset, datasets_location=gene_csv.parent) as ctx:
        rows = list(ctx.stream("genes"))
    assert len(rows) == 2
    assert rows[0]["ensembl_id"] == "ENSG00000139618"
    assert rows[0]["symbol"] == "BRCA2"


def test_stream_with_field_subset(minimal_croissant: Path, gene_csv: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    with AcquisitionContext(dataset, datasets_location=gene_csv.parent) as ctx:
        rows = list(ctx.stream("genes", fields=["ensembl_id"]))
    assert all(set(row.values.keys()) == {"ensembl_id"} for row in rows)


def test_passthrough_transform() -> None:
    row = RecordRow(record_set="genes", values={"ensembl_id": "ENSG00000139618"})
    assert passthrough("ensembl_id")(row) == "ENSG00000139618"


def test_as_curie_transform() -> None:
    row = RecordRow(record_set="genes", values={"ensembl_id": "ENSG0001"})
    assert as_curie(prefix="ensembl", field="ensembl_id")(row) == "ensembl:ENSG0001"
    empty = RecordRow(record_set="genes", values={"ensembl_id": ""})
    assert as_curie(prefix="ensembl", field="ensembl_id")(empty) is None


def test_hash_id_stable_and_collision_free() -> None:
    row_a = RecordRow(record_set="genes", values={"a": "1", "b": "2"})
    row_b = RecordRow(record_set="genes", values={"a": "12", "b": ""})
    h = hash_id("a", "b", prefix="g")
    assert h(row_a) != h(row_b)
    assert h(row_a) == h(row_a)
    assert h(row_a).startswith("g:")


def test_missing_record_set_raises(minimal_croissant: Path, gene_csv: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    with AcquisitionContext(dataset, datasets_location=gene_csv.parent) as ctx:
        with pytest.raises(KeyError):
            list(ctx.stream("nope"))
