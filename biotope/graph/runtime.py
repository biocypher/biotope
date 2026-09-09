"""Explicit execution and integrity checks, without source-format readers."""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TypeVar

from biotope.graph.contracts import Evidence, GraphRecord, Loader, Mapping, Pipeline, SourceContract, SourceRecord
from biotope.graph.sources import digest
from biotope.graph.topology import concept_id, identifier, validate_value


C = TypeVar("C")
T = TypeVar("T")


@dataclass
class ExclusionFinding:
    """One policy count and a bounded sample of its contributing references."""

    count: int = 0
    evidence_sample: list[Evidence] = field(default_factory=list[Evidence])
    evidence_truncated: bool = False


class RunContext:
    """Validated output collection and helpers for explicit project composition.

    Loaders may stream. This selected implementation retains graph objects,
    identities and evidence in memory for deduplication and endpoint checks.
    Projects own join memory and scientific exclusion policies.
    """

    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline
        self.schema = pipeline.topology.describe()
        self.nodes: dict[str, GraphRecord] = {}
        self.edges: dict[str, GraphRecord] = {}
        self._exclusions: dict[str, ExclusionFinding] = {}
        self.loaded: dict[str, int] = {}
        self.source_versions: set[tuple[str, str]] = set()

    def load(self, source: SourceContract, loader: Loader[C, T], config: C) -> Iterator[SourceRecord[T]]:
        """Invoke a registered source's project loader and validate each result."""
        if source not in self.pipeline.sources:
            raise ValueError(f"Unregistered source {source.name}")
        try:
            for record in loader(config):
                if type(record.value) not in source.records:
                    raise ValueError(f"{source.name}: loader returned an undeclared record type {type(record.value)}")
                self._evidence(record.evidence)
                location = f"{source.name} {record.evidence}"
                validate_value(record.value, type(record.value), location)
                record_set = getattr(type(record.value), "__record_set__", None)
                if not any(item.record_set == record_set for item in record.evidence):
                    raise ValueError(f"{location}: evidence does not identify record set {record_set}")
                self.loaded[source.name] = self.loaded.get(source.name, 0) + 1
                yield record
        except Exception as exc:
            raise ValueError(f"{source.name} ({source.metadata}): loader or source contract failed: {exc}") from exc

    def apply(self, mapping: Mapping, *inputs: SourceRecord[object]) -> Iterator[SourceRecord[object]]:
        """Retain all mapping-call inputs on every output, without inferring field lineage."""
        if mapping not in self.pipeline.mappings:
            raise ValueError(f"Unregistered mapping {mapping.name}")
        if len(inputs) != len(mapping.inputs):
            raise ValueError(f"{mapping.name}: expected {len(mapping.inputs)} inputs")
        evidence = tuple(sorted({item for record in inputs for item in record.evidence}))
        self._evidence(evidence)
        for i, (record, expected) in enumerate(zip(inputs, mapping.inputs)):
            validate_value(record.value, expected, f"{mapping.name} input {i} {record.evidence}")
        for output in mapping.function(*(record.value for record in inputs)):
            if type(output) not in mapping.outputs:
                raise ValueError(f"{mapping.name}: undeclared output {type(output)}")
            validate_value(output, type(output), f"{mapping.name} output {evidence}")
            yield SourceRecord(output, evidence)

    def map(self, mapping: Mapping, *inputs: SourceRecord[object]) -> None:
        """Apply a mapping that produces final graph objects and collect its outputs."""
        for output in self.apply(mapping, *inputs):
            self.emit(output.value, output.evidence, mapping=mapping.name)

    def _evidence(self, evidence: tuple[Evidence, ...]) -> None:
        if not evidence or any(
            not all((e.artifact.strip(), e.version.strip(), e.record_set.strip(), e.location.strip())) for e in evidence
        ):
            raise ValueError(
                "Every graph/source record needs source evidence with artifact, version, record set and location"
            )

        self.source_versions.update((item.artifact, item.version) for item in evidence)

    def emit(self, value: object, evidence: tuple[Evidence, ...], *, mapping: str) -> None:
        """Validate and collect a graph object; exact duplicates combine evidence."""
        declaration = next((item for item in self.pipeline.mappings if item.name == mapping), None)
        if declaration is None or type(value) not in declaration.outputs:
            raise ValueError(f"{mapping}: unregistered mapping or undeclared output {type(value)}")
        self._evidence(evidence)
        cls = type(value)
        if cls not in (*self.pipeline.topology.nodes, *self.pipeline.topology.edges):
            raise ValueError(f"{cls}: output is absent from topology")
        validate_value(value, cls, f"{mapping} {evidence}")
        semantic = concept_id(cls)
        edge = cls in self.pipeline.topology.edges
        if edge:
            source = identifier(getattr(value, "source"))
            target = identifier(getattr(value, "target"))
            identity = (
                identifier(getattr(value, "id"))
                if hasattr(value, "id")
                else "edge:" + digest([semantic, source, target])
            )
            store = self.edges
        else:
            identity = identifier(getattr(value, "id"))
            store = self.nodes
        existing = store.get(identity)
        if existing is not None:
            if existing.value != value:
                raise ValueError(
                    f"Conflicting values for {semantic} {identity}; "
                    "resolve the conflict explicitly in the project pipeline"
                )
            existing.evidence.update(evidence)
            existing.mappings.add(mapping)
        else:
            store[identity] = GraphRecord(deepcopy(value), set(evidence), {mapping})

    def exclude(self, reason: str, evidence: tuple[Evidence, ...], *, count: int = 1) -> None:
        """Report a declared exclusion/unmatched-input policy and its source context."""
        self._evidence(evidence)
        if reason not in self.pipeline.policies or type(count) is not int or count < 1:
            raise ValueError("Exclusions require a declared policy key and positive integer count")
        finding = self._exclusions.setdefault(reason, ExclusionFinding())
        finding.count += count
        for item in evidence:
            if item in finding.evidence_sample:
                continue
            if len(finding.evidence_sample) < 10:
                finding.evidence_sample.append(item)
            else:
                finding.evidence_truncated = True

    @property
    def findings(self) -> list[dict[str, object]]:
        """Summarize exclusions; projects may keep full contributor artifacts themselves."""
        return [
            {
                "kind": "exclusion",
                "policy": policy,
                "count": finding.count,
                "evidence_sample": [e.__dict__ for e in finding.evidence_sample],
                "evidence_truncated": finding.evidence_truncated,
            }
            for policy, finding in sorted(self._exclusions.items())
        ]

    def validate_references(self) -> None:
        """Require every emitted edge endpoint to resolve to its declared node kind."""
        for identity, record in self.edges.items():
            schema = self.schema[concept_id(type(record.value))]
            for endpoint in ("source", "target"):
                node_id = getattr(record.value, endpoint)
                node = self.nodes.get(node_id)
                if node is None or concept_id(type(node.value)) != schema[endpoint]:
                    raise ValueError(f"{identity}: unresolved {endpoint} {node_id!r}; expected {schema[endpoint]}")
