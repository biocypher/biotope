"""Explicit execution and integrity checks, without source-format readers."""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from types import MappingProxyType
from typing import Any, ParamSpec, TypeVar, cast

from biotope.graph.contracts import (
    Audit,
    Evidence,
    GraphObject,
    GraphRecord,
    GraphStores,
    GraphView,
    Loader,
    Mapping,
    MappingEntry,
    Pipeline,
    SourceContract,
    SourceRecord,
)
from biotope.graph.signatures import MappingContract, contract
from biotope.graph.sources import digest
from biotope.graph.topology import concept_id, identifier, validate_value


C = TypeVar("C")
T = TypeVar("T")
E = TypeVar("E")
G = TypeVar("G", bound=GraphObject)
P = ParamSpec("P")

EVIDENCE_SAMPLE = 10
"""How many contributor references a bounded report sample keeps."""


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
        self._audits: dict[str, Audit] = {}
        self.loaded: dict[str, int] = {}
        self.source_versions: set[tuple[str, str]] = set()

    def stores(self) -> GraphStores:
        """Borrow the live stores for package measurement."""
        return GraphStores(
            MappingProxyType(self.schema),
            MappingProxyType(self.nodes),
            MappingProxyType(self.edges),
            MappingProxyType(self.pipeline.requirements),
        )

    def view(self) -> GraphView:
        """Build an isolated view for a project validation check."""
        return GraphView(self.stores())

    def snapshot(self) -> tuple[Audit, ...]:
        """Copy the recorded audits so a project check cannot edit the run's own account."""
        return deepcopy(self.audits)

    def content_digest(self) -> str:
        """Fingerprint the schema, the audits and every collected object."""
        return digest(
            [
                self.schema,
                [asdict(item) for item in self.audits],
                [
                    [kind, identity, concept_id(type(row.value)), asdict(cast("Any", row.value))]
                    for kind, store in (("node", self.nodes), ("edge", self.edges))
                    for identity, row in sorted(store.items())
                ],
            ]
        )

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

    # The framework's own parameters are positional-only, so a mapping stays free to
    # name a keyword-only input "mapping" (or "self") without colliding with the call.
    def apply(self, mapping: Mapping[P, E], /, *args: P.args, **kwargs: P.kwargs) -> Iterator[SourceRecord[E]]:
        """Check the call against the mapping's signature; retain all its inputs on every output."""
        resolved = self._resolve(mapping)
        evidence = self._bind(resolved, args, kwargs)
        for output in mapping.function(*args, **kwargs):
            if type(output) not in resolved.outputs:
                raise ValueError(f"{resolved.name}: undeclared output {type(output).__name__}")
            validate_value(output, type(output), f"{resolved.name} output {evidence}")
            yield SourceRecord(output, evidence)

    def map(self, mapping: Mapping[P, G], /, *args: P.args, **kwargs: P.kwargs) -> None:
        """Apply a mapping that produces final graph objects and collect its outputs."""
        for output in self.apply(mapping, *args, **kwargs):
            self._collect(output.value, output.evidence, mapping.name)

    def _resolve(self, mapping: MappingEntry) -> MappingContract:
        if mapping not in self.pipeline.mappings:
            raise ValueError(f"Unregistered mapping {mapping.name}")
        return contract(mapping)

    def _bind(
        self, resolved: MappingContract, args: tuple[object, ...], kwargs: dict[str, object]
    ) -> tuple[Evidence, ...]:
        """Validate the arguments and their values, then combine their contributors."""
        try:
            bound = resolved.signature.bind(*args, **kwargs)
        except TypeError as exc:
            raise ValueError(f"{resolved.name}: {exc}") from exc
        records: list[SourceRecord[object]] = []
        for parameter in resolved.parameters:
            given = bound.arguments[parameter.name]
            subject = f"{resolved.name} input {parameter.name!r}"
            if not isinstance(given, SourceRecord):
                raise ValueError(f"{subject}: expected a SourceRecord, got {type(given).__name__}")
            record = cast("SourceRecord[object]", given)
            # Per input: one contributor-bearing record must never cover for another.
            self._evidence(record.evidence, subject)
            location = f"{subject} {record.evidence}"
            accepted = next((item for item in parameter.accepts if type(record.value) is item), None)
            if accepted is None:
                raise ValueError(
                    f"{location}: expected {' | '.join(item.__name__ for item in parameter.accepts)}, "
                    f"got {type(record.value).__name__}"
                )
            validate_value(record.value, accepted, location)
            records.append(record)
        return tuple(sorted({item for record in records for item in record.evidence}))

    def _evidence(self, evidence: tuple[Evidence, ...], subject: str = "") -> None:
        if not evidence or any(
            not all((e.artifact.strip(), e.version.strip(), e.record_set.strip(), e.location.strip())) for e in evidence
        ):
            prefix = f"{subject}: " if subject else ""
            raise ValueError(
                prefix
                + "Every graph/source record needs source evidence with artifact, version, record set and location"
            )

        self.source_versions.update((item.artifact, item.version) for item in evidence)

    def _collect(self, value: GraphObject, evidence: tuple[Evidence, ...], mapping: str) -> None:
        """Validate and collect a graph object; exact duplicates combine evidence."""
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
            if len(finding.evidence_sample) < EVIDENCE_SAMPLE:
                finding.evidence_sample.append(item)
            else:
                finding.evidence_truncated = True

    def record_audit(
        self,
        stage: str,
        *,
        inputs: str,
        outputs: str,
        selection: str,
        counts: dict[str, int],
        evidence: tuple[Evidence, ...] = (),
        notes: tuple[str, ...] = (),
    ) -> None:
        """Record what one stage read, at what grain, under which selection rule.

        Name every count the stage actually needs to be checkable, including the
        rows it considered and did not emit. Biotope imposes no arithmetic between
        them: state the grains and let a validation check compare the counts with
        an expectation derived from the source.
        """
        if stage in self._audits:
            raise ValueError(f"Stage {stage!r} is already recorded; give each recorded stage its own identity")
        for label, text in (("stage", stage), ("inputs", inputs), ("outputs", outputs), ("selection", selection)):
            if not text.strip():
                raise ValueError(f"An audit needs a non-empty {label}; describe the grain and the selection rule")
        for key, value in counts.items():
            if not key.strip() or type(value) is not int or value < 0:
                raise ValueError(f"Audit count {key!r} must be a named non-negative integer, not {value!r}")
        if evidence:
            self._evidence(evidence)
        self._audits[stage] = Audit(
            stage=stage,
            inputs=inputs,
            outputs=outputs,
            selection=selection,
            counts=dict(counts),
            evidence_sample=tuple(sorted(set(evidence)))[:EVIDENCE_SAMPLE],
            evidence_truncated=len(set(evidence)) > EVIDENCE_SAMPLE,
            notes=notes,
        )

    @property
    def audits(self) -> tuple[Audit, ...]:
        """Recorded stage accounts, in the order the pipeline recorded them."""
        return tuple(self._audits.values())

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
