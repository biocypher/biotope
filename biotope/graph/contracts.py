"""Small contracts shared by project-owned loading, mapping and execution."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar

from biotope.graph.topology import Topology


if TYPE_CHECKING:
    from biotope.graph.runtime import RunContext

T = TypeVar("T", covariant=True)
C = TypeVar("C", contravariant=True)


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


@dataclass(frozen=True)
class Mapping:
    """An authored function and explicit input/output contracts, registered by ID."""

    name: str
    function: Callable[..., Iterable[object]]
    inputs: tuple[type, ...]
    outputs: tuple[type, ...]
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
    mappings: tuple[Mapping, ...]
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
