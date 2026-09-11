"""Measurements of typed outputs and execution without an export dependency."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar, NewType

import pytest

from biotope.graph import Evidence, Mapping, Pipeline, SourceRecord, Topology
from biotope.graph.runtime import RunContext


NodeId = NewType("NodeId", str)
UnusedId = NewType("UnusedId", str)


@dataclass(frozen=True)
class NodeRow:
    """A synthetic source row behind one measured node."""

    index: int
    name: str | None
    tags: list[str]


@dataclass(frozen=True)
class LinkRow:
    """A synthetic source row behind one measured edge."""

    index: int
    source: int
    target: int


@dataclass(frozen=True)
class Node:
    schema_id: ClassVar[str] = "test:node"
    id: NodeId
    name: str | None = None
    count: int = 0
    enabled: bool = False
    tags: list[str] | None = None


@dataclass(frozen=True)
class Unused:
    schema_id: ClassVar[str] = "test:unused"
    id: UnusedId
    note: str | None = None


@dataclass(frozen=True)
class Link:
    schema_id: ClassVar[str] = "test:link"
    id: str
    source: NodeId
    target: NodeId


def make_node(row: SourceRecord[NodeRow]) -> Iterator[Node]:
    """Produce one node with the row's own name and tag values."""
    yield Node(NodeId(f"n:{row.value.index}"), row.value.name, tags=row.value.tags)


def make_link(row: SourceRecord[LinkRow]) -> Iterator[Link]:
    """Produce one edge between two node identifiers."""
    yield Link(f"e:{row.value.index}", NodeId(f"n:{row.value.source}"), NodeId(f"n:{row.value.target}"))


NODES = Mapping(name="nodes", function=make_node)
EDGES = Mapping(name="edges", function=make_link)


def node(index: int, name: str | None, tags: list[str]) -> SourceRecord[NodeRow]:
    """One evidence-bearing node row."""
    return SourceRecord(NodeRow(index, name, tags), (Evidence("rows", "v1", "nodes", str(index)),))


def link(index: int, source: int, target: int) -> SourceRecord[LinkRow]:
    """One evidence-bearing edge row."""
    return SourceRecord(LinkRow(index, source, target), (Evidence("rows", "v1", "edges", str(index)),))


def emit_fixture(context: RunContext) -> None:
    """Build the measured fixture graph through the checked mapping path."""
    for index, name in enumerate((None, "  ", "x" * 200, "fourth")):
        context.map(NODES, node(index, name, []))
    for index, (source, target) in enumerate(((0, 1), (0, 1), (1, 1))):
        context.map(EDGES, link(index, source, target))


PIPELINE = Pipeline(
    "fixture",
    Topology((Node, Unused), (Link,)),
    (),
    (NODES, EDGES),
    emit_fixture,
    scope="four nodes and three edges",
    code_paths=(__file__,),
    requirements={"entity:unused": "test:unused"},
)


def test_quality_counts_evidence_and_empty_denominators():
    from biotope.graph.quality import GraphView, analyze_quality

    context = RunContext(PIPELINE)
    emit_fixture(context)
    context.validate_references()
    report = analyze_quality(GraphView(context.schema, context.nodes, context.edges, PIPELINE.requirements)).to_json()
    m = report["measurements"]
    assert m["population"] == {"test:node": 4, "test:unused": 0, "test:link": 3}
    names = m["properties"]["test:node"]["name"]
    assert (names["null"], names["blank"], names["missing"], names["total"]) == (1, 1, 2, 4)
    assert names["examples"][1] == {"value": "x" * 160, "truncated": True}
    assert m["properties"]["test:node"]["count"]["missing"] == 0
    assert m["properties"]["test:node"]["enabled"]["missing"] == 0
    assert m["properties"]["test:node"]["tags"]["empty_list"] == 4
    assert m["properties"]["test:unused"]["note"]["missing_rate"] is None
    assert m["connectivity"]["components"] == 3
    assert m["connectivity"]["size_distribution"] == {"1": 2, "2": 1}
    assert m["connectivity"]["isolated_total"] == 2
    assert m["connectivity"]["largest_share"] == 0.5
    assert m["concentration"]["test:link"]["target"]["top"][0] == {"id": "n:1", "count": 3, "share": 1.0}
    assert m["self_loops"]["test:link"] == {"count": 1, "total": 3, "rate": 1 / 3}
    loop = next(f for f in report["findings"] if f["code"] == "quality.self_loop")
    assert loop["examples"][0]["id"] == "e:2"
    assert loop["examples"][0]["evidence"][0]["location"] == "2"
    assert {"quality.empty_required", "quality.missing_property", "quality.self_loop"} <= {
        f["code"] for f in report["findings"]
    }

    context.map(NODES, node(4, None, ["v" * 200] * 8))
    bounded = analyze_quality(GraphView(context.schema, context.nodes, context.edges, {})).to_json()
    values = bounded["measurements"]["properties"]["test:node"]["tags"]["examples"]
    assert values[-1] == {"value": ["v" * 160] * 5, "truncated": True}

    empty = analyze_quality(GraphView(context.schema, {}, {}, {})).to_json()["measurements"]
    assert empty["connectivity"]["largest_share"] is None
    assert empty["self_loops"]["test:link"]["rate"] is None


def test_quality_executes_once_without_export_and_records_failures(tmp_path, monkeypatch):
    import json
    from dataclasses import replace

    from biotope.graph import build
    from biotope.graph.reports import CheckFailed

    calls = []

    def run(context):
        calls.append("run")
        emit_fixture(context)

    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked", "topology_digest": "fixture"})

    class ForbiddenWriter:
        def __init__(self):
            raise AssertionError("Quality instantiated BioCypher")

    monkeypatch.setattr(build, "BioCypherWriter", ForbiddenWriter)
    report_path = tmp_path / "graph/reports/quality.json"
    report = build.assess_pipeline(replace(PIPELINE, run=run), report_path)
    assert calls == ["run"]
    assert report["operation"] == "quality" and report["state"] == "complete"
    assert report["outputs"] == []
    assert report["quality"]["measurements"]["population"]["test:node"] == 4
    assert json.loads(report_path.read_text())["quality"] == report["quality"]
    assert list(report_path.parent.iterdir()) == [report_path]

    class Writer:
        def check_environment(self):
            calls.append("environment")
            return {"exporter": "test", "version": "0", "format": "none"}

        def write(self, context, output, *, query_context):
            calls.append("export")
            return []

    result = build.run_pipeline(replace(PIPELINE, run=run), tmp_path / "build", writer=Writer())
    # The exporter is verified before any project loader runs, not after.
    assert calls == ["run", "environment", "run", "export"]
    assert result["quality"] == report["quality"]

    def bad(context):
        raise ValueError("mapping failed")

    with pytest.raises(ValueError, match="mapping failed"):
        build.assess_pipeline(replace(PIPELINE, run=bad), report_path)
    assert json.loads(report_path.read_text())["quality"]["state"] == "not_run"

    def dangling(context):
        context.map(EDGES, link(99, 98, 97))

    with pytest.raises(ValueError):
        build.assess_pipeline(replace(PIPELINE, run=dangling), report_path)
    failure = json.loads(report_path.read_text())
    assert failure["quality"]["state"] == "not_run"
    assert failure["quality"]["blocked_by"] == "integrity.failed"
    assert "measurements" not in failure["quality"]

    def invalid(*a, **kw):
        raise CheckFailed({"state": "failed", "findings": [{"severity": "error", "message": "stale"}]})

    monkeypatch.setattr(build, "check_pipeline", invalid)
    with pytest.raises(ValueError, match="stale"):
        build.assess_pipeline(PIPELINE, report_path)
    assert json.loads(report_path.read_text())["definitions"]["state"] == "failed"
    report_path.write_text('{"authored": true}')
    with pytest.raises(ValueError, match="authored|generated"):
        build.assess_pipeline(PIPELINE, report_path)
    assert json.loads(report_path.read_text()) == {"authored": True}
