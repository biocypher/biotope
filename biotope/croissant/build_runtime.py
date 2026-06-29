"""Runtime helpers for generated ``create_knowledge_graph.py`` builds."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from biotope.croissant.mapping.compile import CompileStats, EdgeTuple, NodeTuple


def purge_biocypher_output(build_dir: Path) -> None:
    """Remove prior BioCypher output so re-runs don't append stale CSV/Neo4j files."""
    out = build_dir / "biocypher-out"
    if out.exists():
        shutil.rmtree(out)


def compute_orphan_metrics(
    nodes: Iterable[NodeTuple],
    edges: Iterable[EdgeTuple],
) -> dict[str, Any]:
    """Count edges whose endpoints are missing from the emitted node id set."""
    node_ids = {node_id for node_id, _, _ in nodes}
    edge_list = list(edges)
    by_relationship: Counter[str] = Counter()
    for _, src, tgt, label, _ in edge_list:
        if src not in node_ids or tgt not in node_ids:
            by_relationship[label] += 1
    orphaned = sum(by_relationship.values())
    return {
        "orphaned_count": orphaned,
        "total_edges": len(edge_list),
        "importable_edges": len(edge_list) - orphaned,
        "by_relationship": dict(by_relationship),
    }


def write_build_metrics(build_dir: Path, metrics: dict[str, Any]) -> Path:
    """Write ``build_metrics.json`` under ``biocypher-out/``."""
    out = build_dir / "biocypher-out"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "build_metrics.json"
    path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return path


def load_build_metrics(build_dir: Path) -> dict[str, Any] | None:
    """Load ``build_metrics.json`` when present."""
    path = build_dir / "biocypher-out" / "build_metrics.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
