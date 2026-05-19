from pathlib import Path

from biotope.croissant.spec import CroissantFileObjectModel, FieldKind, load_from_path


def test_load_minimal(minimal_croissant: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    assert dataset.name == "minimal"
    assert len(dataset.record_set) == 1
    rs = dataset.record_set[0]
    assert rs.name == "genes"
    assert [f.name for f in rs.field] == ["ensembl_id", "symbol", "biotype"]
    assert all(f.kind() == FieldKind.STRING for f in rs.field)


def test_distribution_round_trip(minimal_croissant: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    assert len(dataset.distribution) == 1
    dist = dataset.distribution[0]
    assert isinstance(dist, CroissantFileObjectModel)
    assert dist.id == "genes"
    assert dist.content_url == "genes.csv"


def test_record_set_by_name(two_recordsets_croissant: Path) -> None:
    dataset = load_from_path(two_recordsets_croissant)
    assert dataset.record_set_by_name("genes") is not None
    assert dataset.record_set_by_name("does_not_exist") is None
