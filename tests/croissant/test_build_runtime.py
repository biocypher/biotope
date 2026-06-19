"""Tests for build runtime helpers."""

from biotope.croissant.build_runtime import compute_orphan_metrics, purge_biocypher_output, write_build_metrics


def test_compute_orphan_metrics(tmp_path) -> None:
    nodes = [("n1", "gene", {}), ("n2", "gene", {})]
    edges = [
        (None, "n1", "n2", "link", {}),
        (None, "n1", "missing", "dangling", {}),
    ]
    metrics = compute_orphan_metrics(nodes, edges)
    assert metrics["total_edges"] == 2
    assert metrics["orphaned_count"] == 1
    assert metrics["importable_edges"] == 1
    assert metrics["by_relationship"] == {"dangling": 1}


def test_purge_and_write_build_metrics(tmp_path) -> None:
    build_dir = tmp_path / "build"
    out = build_dir / "biocypher-out"
    out.mkdir(parents=True)
    stale = out / "Tool.csv"
    stale.write_text("stale\n")

    purge_biocypher_output(build_dir)
    assert not out.exists()

    path = write_build_metrics(build_dir, {"orphaned_count": 0, "total_edges": 0, "importable_edges": 0})
    assert path.is_file()
    assert "build_metrics.json" in path.name
