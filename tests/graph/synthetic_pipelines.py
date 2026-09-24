"""Synthetic pipelines and a recording writer for the build, export and quality tests."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, NewType

from biotope.graph import Evidence, Mapping, Pipeline, SourceRecord, Topology
from biotope.graph.runtime import RunContext


FindingId = NewType("FindingId", str)
StudyId = NewType("StudyId", str)


@dataclass(frozen=True)
class ResultRow:
    __record_set__: ClassVar[str] = "results"
    key: str


@dataclass(frozen=True)
class Result:
    """One reported result."""

    schema_id: ClassVar[str] = "study:result.v1"
    id: FindingId
    effect: float = field(metadata={"description": "Log2 fold change, treated over control."})
    note: str | None = None


@dataclass(frozen=True)
class Study:
    """The study that reported a result."""

    schema_id: ClassVar[str] = "study:source"
    id: StudyId


@dataclass(frozen=True)
class ReportedBy:
    """Links a result to the study that reported it."""

    schema_id: ClassVar[str] = "study:reported-by"
    source: FindingId
    target: StudyId


def report_result(row: SourceRecord[ResultRow]) -> tuple[Result, Study, ReportedBy]:
    finding, study = FindingId("result:" + row.value.key), StudyId("study:one")
    return Result(finding, 1.5, "reviewed"), Study(study), ReportedBy(finding, study)


RESULTS = Mapping(name="results", function=report_result)


def result_row(key: str, artifact: str = "rows") -> SourceRecord[ResultRow]:
    return SourceRecord(ResultRow(key), (Evidence(artifact, "v1", "results", key),))


def emit_results(context: RunContext, keys: Iterable[str] = ("a",)) -> None:
    for key in keys:
        context.map(RESULTS, result_row(key))


RESULTS_PIPELINE = Pipeline(
    "results",
    Topology((Result, Study), (ReportedBy,)),
    (),
    (RESULTS,),
    emit_results,
    scope="synthetic results",
    code_paths=(__file__,),
)


NodeId = NewType("NodeId", str)
UnusedId = NewType("UnusedId", str)


@dataclass(frozen=True)
class NodeRow:
    index: int
    name: str | None
    tags: list[str]


@dataclass(frozen=True)
class LinkRow:
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
    yield Node(NodeId(f"n:{row.value.index}"), row.value.name, tags=row.value.tags)


def make_link(row: SourceRecord[LinkRow]) -> Iterator[Link]:
    yield Link(f"e:{row.value.index}", NodeId(f"n:{row.value.source}"), NodeId(f"n:{row.value.target}"))


NODES = Mapping(name="nodes", function=make_node)
EDGES = Mapping(name="edges", function=make_link)


def node(index: int, name: str | None, tags: list[str]) -> SourceRecord[NodeRow]:
    return SourceRecord(NodeRow(index, name, tags), (Evidence("rows", "v1", "nodes", str(index)),))


def link(index: int, source: int, target: int) -> SourceRecord[LinkRow]:
    return SourceRecord(LinkRow(index, source, target), (Evidence("rows", "v1", "edges", str(index)),))


def emit_measured(context: RunContext) -> None:
    for index, name in enumerate((None, "  ", "x" * 200, "fourth")):
        context.map(NODES, node(index, name, []))
    for index, (source, target) in enumerate(((0, 1), (0, 1), (1, 1))):
        context.map(EDGES, link(index, source, target))


MEASURED_PIPELINE = Pipeline(
    "measured",
    Topology((Node, Unused), (Link,)),
    (),
    (NODES, EDGES),
    emit_measured,
    scope="four nodes and three edges",
    code_paths=(__file__,),
    requirements={"entity:unused": "test:unused"},
)


class RecordingWriter:
    def __init__(self, calls: list[str] | None = None) -> None:
        self.calls = [] if calls is None else calls

    def check_environment(self) -> dict[str, object]:
        self.calls.append("environment")
        return {"exporter": "test", "version": "0", "format": "text"}

    def write(self, context: RunContext, directory: Path) -> list[str]:
        self.calls.append("export")
        (directory / "artifact.txt").write_text(str(len(context.nodes)))
        return ["artifact.txt"]
