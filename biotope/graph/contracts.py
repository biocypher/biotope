"""Small contracts shared by project-owned loading, mapping and execution."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Generic, ParamSpec, Protocol, TypeVar

from biotope.graph.topology import Topology


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


@dataclass
class GraphRecord:
    """One validated graph object with combined evidence and mapping references."""

    value: object
    evidence: set[Evidence] = field(default_factory=set[Evidence])
    mappings: set[str] = field(default_factory=set[str])
