"""Advisory measurements of validated graph objects, independent of execution/I/O."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import asdict
from heapq import nsmallest
from typing import Any, cast

from biotope.graph.contracts import GraphRecord, GraphView
from biotope.graph.reports import Finding, FindingSink, Phase, QualityReport
from biotope.graph.topology import concept_id


__all__ = ["CHECKS", "GraphView", "analyze_quality"]


def _records(view: GraphView) -> Iterator[tuple[str, GraphRecord]]:
    yield from view.nodes.items()
    yield from view.edges.items()


def _example(identity: str, row: GraphRecord) -> dict[str, object]:
    return {
        "id": identity,
        "mappings": nsmallest(3, row.mappings),
        "mappings_truncated": len(row.mappings) > 3,
        "evidence": [asdict(e) for e in nsmallest(3, row.evidence)],
        "evidence_truncated": len(row.evidence) > 3,
    }


def _bounded(value: object) -> dict[str, object]:
    truncated = False
    if isinstance(value, str):
        truncated = len(value) > 160
        value = value[:160]
    elif isinstance(value, list):
        items = cast(list[object], value)
        bounded = [_bounded(v) for v in items[:5]]
        truncated = len(items) > 5 or any(v["truncated"] for v in bounded)
        value = [v["value"] for v in bounded]
    return {"value": value, "truncated": truncated}


def population(view: GraphView, report: QualityReport) -> None:
    counts = dict.fromkeys(view.concepts, 0)
    for _, row in _records(view):
        counts[concept_id(type(row.value))] += 1
    report.measurements["population"] = counts
    for concept in sorted(set(view.requirements.values())):
        if concept in counts and counts[concept] == 0:
            report.findings.append(
                Finding("quality.empty_required", "warning", concept, "No emitted records for this required concept")
            )


def properties(view: GraphView, report: QualityReport) -> None:
    results: dict[str, Any] = {
        concept: {
            name: {
                "total": 0,
                "null": 0,
                "blank": 0,
                "empty_list": 0,
                "missing": 0,
                "missing_rate": None,
                "examples": [],
            }
            for name in schema["properties"]
        }
        for concept, schema in view.concepts.items()
    }
    # These lists borrow at most three existing values per property; reports contain bounded copies.
    seen: dict[tuple[str, str], list[object]] = {}
    examples: dict[str, list[dict[str, object]]] = {}
    for identity, row in _records(view):
        concept = concept_id(type(row.value))
        samples = examples.setdefault(concept, [])
        if len(samples) < 3:
            samples.append(_example(identity, row))
        for name, stats in results[concept].items():
            value = getattr(row.value, name)
            stats["total"] += 1
            key = (
                "null"
                if value is None
                else "blank"
                if isinstance(value, str) and not value.strip()
                else "empty_list"
                if isinstance(value, list) and not value
                else None
            )
            if key:
                stats[key] += 1
                stats["missing"] += 1
            previous = seen.setdefault((concept, name), [])
            if value is not None and len(previous) < 3 and value not in previous:
                previous.append(cast(object, value))
                stats["examples"].append(_bounded(cast(object, value)))
    for concept, props in results.items():
        for name, stats in props.items():
            for key in ("null", "blank", "empty_list", "missing"):
                stats[key + "_rate"] = stats[key] / stats["total"] if stats["total"] else None
            if stats["total"] and stats["missing"] == stats["total"]:
                report.findings.append(
                    Finding(
                        "quality.missing_property",
                        "warning",
                        f"{concept}.{name}",
                        f"All {stats['total']} records lack a usable value: {stats['null']} null, "
                        f"{stats['blank']} blank, {stats['empty_list']} empty list",
                        examples=tuple(examples[concept]),
                    )
                )
    report.measurements["properties"] = results


def connectivity(view: GraphView, report: QualityReport) -> None:
    parent = {key: key for key in view.nodes}
    sizes = dict.fromkeys(view.nodes, 1)
    isolated = set(view.nodes)

    def root(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for row in view.edges.values():
        source, target = str(getattr(row.value, "source")), str(getattr(row.value, "target"))
        isolated.discard(source)
        isolated.discard(target)
        a, b = root(source), root(target)
        if a != b:
            if sizes[a] < sizes[b]:
                a, b = b, a
            parent[b] = a
            sizes[a] += sizes.pop(b)
    distribution = Counter(sizes.values())
    kinds = Counter(concept_id(type(view.nodes[i].value)) for i in isolated)
    report.measurements["connectivity"] = {
        "components": len(sizes),
        "size_distribution": {str(k): v for k, v in sorted(distribution.items())},
        "largest_size": max(sizes.values(), default=0),
        "largest_share": max(sizes.values()) / len(view.nodes) if view.nodes else None,
        "isolated_total": len(isolated),
        "isolated_by_type": dict(sorted(kinds.items())),
        "examples": [_example(i, view.nodes[i]) for i in nsmallest(3, isolated)],
    }


def concentration(view: GraphView, report: QualityReport) -> None:
    counts: dict[str, dict[str, Counter[str]]] = {
        k: {"source": Counter(), "target": Counter()} for k, s in view.concepts.items() if s["kind"] == "edge"
    }
    for row in view.edges.values():
        for side, counter in counts[concept_id(type(row.value))].items():
            counter[str(getattr(row.value, side))] += 1
    report.measurements["concentration"] = {
        concept: {
            side: {
                "total": sum(counter.values()),
                "distinct": len(counter),
                "top": [
                    {"id": identity, "count": count, "share": count / sum(counter.values())}
                    for identity, count in nsmallest(3, counter.items(), key=lambda item: (-item[1], item[0]))
                ],
            }
            for side, counter in sides.items()
        }
        for concept, sides in counts.items()
    }


def self_loops(view: GraphView, report: QualityReport) -> None:
    counts = {k: {"count": 0, "total": 0} for k, s in view.concepts.items() if s["kind"] == "edge"}
    examples: dict[str, list[dict[str, object]]] = {}
    for identity, row in view.edges.items():
        concept = concept_id(type(row.value))
        counts[concept]["total"] += 1
        if getattr(row.value, "source") == getattr(row.value, "target"):
            counts[concept]["count"] += 1
            samples = examples.setdefault(concept, [])
            if len(samples) < 3:
                samples.append(_example(identity, row))
    report.measurements["self_loops"] = {
        k: {**s, "rate": s["count"] / s["total"] if s["total"] else None} for k, s in counts.items()
    }
    for concept, stats in counts.items():
        if stats["count"]:
            report.findings.append(
                Finding(
                    "quality.self_loop",
                    "warning",
                    concept,
                    f"{stats['count']} / {stats['total']} edges connect an identifier to itself",
                    examples=tuple(examples[concept]),
                )
            )


CHECKS: tuple[Callable[[GraphView, QualityReport], None], ...] = (
    population,
    properties,
    connectivity,
    concentration,
    self_loops,
)


def analyze_quality(
    view: GraphView, *, phase: Phase | None = None, on_finding: FindingSink | None = None
) -> QualityReport:
    """Assess final validated objects; scientific thresholds remain project decisions."""
    report = QualityReport()
    for check in CHECKS:
        if phase:
            phase("Quality: " + check.__name__.replace("_", " "))
        start = len(report.findings)
        check(view, report)
        if on_finding:
            for finding in report.findings[start:]:
                on_finding(finding)
    return report
