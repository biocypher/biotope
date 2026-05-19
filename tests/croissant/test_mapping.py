from pathlib import Path

from biotope.croissant.acquisition import AcquisitionContext
from biotope.croissant.spec import load_from_path
from biotope.croissant.mapping import compile_mapping, default_mapping, load_mapping
from biotope.croissant.mapping.loader import dump_mapping


def test_default_mapping_minimal(minimal_croissant: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    mapping = default_mapping(dataset, croissant_path=str(minimal_croissant))
    assert len(mapping.nodes) == 1
    node = mapping.nodes[0]
    assert node.record_set == "genes"
    assert node.type == "genes"
    assert node.id.from_ == "ensembl_id"


def test_default_mapping_fk_edges(two_recordsets_croissant: Path) -> None:
    dataset = load_from_path(two_recordsets_croissant)
    mapping = default_mapping(dataset, croissant_path=str(two_recordsets_croissant))
    # Two record sets → two node types
    node_types = {n.type for n in mapping.nodes}
    assert {"genes", "gene_disease"}.issubset(node_types)
    # gene_disease.gene_id matches genes' id field → at least one edge proposed
    assert any(e.target.from_ == "gene_id" for e in mapping.edges)


def test_round_trip_yaml(minimal_croissant: Path, tmp_path: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    mapping = default_mapping(dataset, croissant_path=str(minimal_croissant))
    yaml_path = tmp_path / "minimal.mapping.yaml"
    dump_mapping(mapping, yaml_path)
    reloaded = load_mapping(yaml_path)
    assert reloaded.nodes[0].record_set == "genes"


def test_compile_and_stream_nodes(minimal_croissant: Path, gene_csv: Path) -> None:
    dataset = load_from_path(minimal_croissant)
    mapping = default_mapping(dataset, croissant_path=str(minimal_croissant))
    with AcquisitionContext(dataset, datasets_location=gene_csv.parent) as ctx:
        adapter = compile_mapping(mapping, ctx)
        nodes = list(adapter.get_nodes())
    assert len(nodes) == 2
    node_ids = {n[0] for n in nodes}
    assert "ENSG00000139618" in node_ids
    assert all(n[1] == "genes" for n in nodes)
