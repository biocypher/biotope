"""Small contracts shared by project-owned loading, mapping and execution."""

from __future__ import annotations

import collections.abc
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Generic, Literal, ParamSpec, Protocol, TypeVar, cast

from biotope.graph.topology import ConceptSchema, Topology


if TYPE_CHECKING:
    from biotope.graph.runtime import RunContext

T = TypeVar("T", covariant=True)
C = TypeVar("C", contravariant=True)
P = ParamSpec("P")
E = TypeVar("E")


@dataclass(frozen=True, order=True)
class Evidence:
    """A resolvable source reference, not a claim of automatic field lineage."""

    artifact: str
    version: str
    record_set: str
    location: str


@dataclass(frozen=True)
class SourceRecord(Generic[T]):
    """A typed record or intermediate accompanied by its contributors."""

    value: T
    evidence: tuple[Evidence, ...]


class Loader(Protocol[C, T]):
    """A project-owned callable with explicit configuration and typed results."""

    def __call__(self, config: C, /) -> Iterable[SourceRecord[T]]:
        """Read source values only when explicitly invoked by a pipeline."""
        ...


@dataclass(frozen=True)
class SourceContract:
    """Participating generated record classes and their effective metadata."""

    name: str
    metadata: Path
    generated: Path
    records: tuple[type, ...]


class GraphObject(Protocol):
    """A topology declaration, recognized by the semantic identity it declares.

    Structural on purpose: node and relation dataclasses already declare
    ``schema_id`` and need no Biotope base class. Membership in the selected
    topology stays a definition and runtime check.
    """

    schema_id: ClassVar[str]


G = TypeVar("G", bound=GraphObject)


class MappingEntry(Protocol):
    """One registration's identity and report metadata, deliberately not callable.

    ``Pipeline.mappings`` holds registrations with unrelated signatures, so it
    exposes this read-only view. Import the concrete ``Mapping`` object to invoke
    it through ``RunContext``; a registry entry offers no dispatch route.
    """

    @property
    def name(self) -> str:
        """Stable project-wide mapping identity."""
        ...

    @property
    def requirements(self) -> tuple[str, ...]:
        """Purpose requirement keys this mapping contributes to."""
        ...

    @property
    def evidence(self) -> tuple[str, ...]:
        """Authored rationale, kept beside the transformation it explains."""
        ...


@dataclass(frozen=True)
class Mapping(Generic[P, E]):
    """An authored function whose signature is the whole mapping contract.

    The parameter specification and the output element type are preserved, so
    composition is checked statically and the runtime/report contracts derive
    from the annotations rather than from a second, independent declaration.
    """

    name: str
    function: Callable[P, Iterable[E]]
    requirements: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class Audit:
    """One stage's own account of what it read, kept and set aside.

    Counts are project-named on purpose. One source row can produce several
    objects, feed an aggregate or be read twice, and an unavailable join can
    limit one output while leaving another intact, so no fixed arithmetic
    relates loaded records to emitted ones. Biotope records and reports the
    account; project validation checks are what interpret it.
    """

    stage: str
    inputs: str
    outputs: str
    selection: str
    counts: dict[str, int]
    evidence_sample: tuple[Evidence, ...] = ()
    evidence_truncated: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class GraphView:
    """Borrowed read-only stores; analysis never constructs a second object graph."""

    concepts: collections.abc.Mapping[str, ConceptSchema]
    nodes: collections.abc.Mapping[str, GraphRecord]
    edges: collections.abc.Mapping[str, GraphRecord]
    requirements: collections.abc.Mapping[str, str]

    def records(self, concept: type[G]) -> Iterator[G]:
        """Iterate the collected objects of one declared type, without copying them."""
        for store in (self.nodes, self.edges):
            for row in store.values():
                if type(row.value) is concept:
                    yield cast(G, row.value)


ValidationState = Literal["passed", "failed", "unverified"]


@dataclass(frozen=True)
class ValidationResult:
    """One check's outcome. ``unverified`` records missing knowledge, never a pass."""

    state: ValidationState
    detail: str
    measurements: dict[str, object] = field(default_factory=dict[str, object])

    @classmethod
    def ok(cls, detail: str, **measurements: object) -> ValidationResult:
        """The expectation was derived independently and the graph met it."""
        return cls("passed", detail, dict(measurements))

    @classmethod
    def wrong(cls, detail: str, **measurements: object) -> ValidationResult:
        """The graph contradicts an expectation the project stands behind; blocks export."""
        return cls("failed", detail, dict(measurements))

    @classmethod
    def unknown(cls, detail: str, **measurements: object) -> ValidationResult:
        """The expectation could not be established; the capability stays unresolved."""
        return cls("unverified", detail, dict(measurements))


@dataclass(frozen=True)
class ValidationCheck:
    """A project check of the built graph against an independently derived expectation.

    Runs after reference integrity and before export. Deriving the expectation
    from the same code that built the graph proves nothing: read the source, a
    published count or a curated answer instead. A failed check blocks export;
    an unverified one leaves its capability unresolved and keeps the rest.
    """

    name: str
    function: Callable[[GraphView, tuple[Audit, ...]], ValidationResult]
    capability: str = ""
    evidence: tuple[str, ...] = ()


InterpretationKind = Literal["selection", "statistic", "identity", "qualifier", "uncertainty"]


@dataclass(frozen=True)
class Interpretation:
    """One rule a reader must apply, bound to the concept or property it governs.

    ``subject`` is a topology concept ID or ``<concept ID>.<property>``. Kinds
    separate what was admitted (``selection``), what a value measures
    (``statistic``), when two identifiers may be joined (``identity``), context
    that changes a claim's meaning (``qualifier``) and what the value does not
    establish (``uncertainty``).
    """

    subject: str
    kind: InterpretationKind
    statement: str
    alternatives: tuple[str, ...] = ()


@dataclass(frozen=True)
class Capability:
    """One question family the graph is claimed to answer, with its stated limits."""

    key: str
    question: str
    concepts: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryExample:
    """A query a consumer can run, kept beside the capability it demonstrates."""

    capability: str
    language: str
    query: str
    expectation: str = ""


@dataclass(frozen=True)
class QueryContext:
    """Interpretation rules delivered with the graph, for a reader who has only the graph.

    The consuming agent receives labels, properties and values, not the
    builder's reasoning. Whatever it must know to select the right comparison,
    read a statistic, join identities or decline an unsupported conclusion
    belongs here, because nothing else travels with the export.
    """

    interpretations: tuple[Interpretation, ...] = ()
    capabilities: tuple[Capability, ...] = ()
    examples: tuple[QueryExample, ...] = ()


@dataclass(frozen=True)
class Pipeline:
    """Explicit project composition; imports must not load data or execute mappings.

    Code paths enumerate the authored Python to check and fingerprint. Requirements
    map ``entity:<intent text>`` / ``relation:<intent text>`` to concept IDs;
    deferrals map the same keys to reasons. Neither changes project intent.
    """

    name: str
    topology: Topology
    sources: tuple[SourceContract, ...]
    mappings: tuple[MappingEntry, ...]
    run: Callable[[RunContext], None]
    scope: str
    code_paths: tuple[str | Path, ...]
    settings: dict[str, object] = field(default_factory=dict[str, object])
    requirements: dict[str, str] = field(default_factory=dict[str, str])
    deferrals: dict[str, str] = field(default_factory=dict[str, str])
    policies: dict[str, str] = field(default_factory=dict[str, str])
    intent: Path | None = None
    dependencies: tuple[str, ...] = ()
    variability: str = "Unspecified; external state and nondeterminism have not been reviewed."
    validation_checks: tuple[ValidationCheck, ...] = ()
    query_context: QueryContext = field(default_factory=QueryContext)


@dataclass
class GraphRecord:
    """One validated graph object with combined evidence and mapping references."""

    value: object
    evidence: set[Evidence] = field(default_factory=set[Evidence])
    mappings: set[str] = field(default_factory=set[str])
