"""Compile a semantic :class:`Mapping` into BioCypher-compatible tuple streams.

Two flat iterator helpers — :func:`iter_entity_tuples` and
:func:`iter_relation_tuples` — drive both the build pipeline and the preview
engine. :func:`compile_mapping` wraps them in a :class:`CompiledAdapter` whose
``get_nodes()`` / ``get_edges()`` methods match the structural protocol
BioCypher accepts.

Tuple shapes (BioCypher conventions):

* entity tuple: ``(node_id, node_label, properties_dict)``
* relation tuple: ``(source_id, target_id, label, type, properties_dict)``
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from biotope.croissant.acquisition.context import AcquisitionContext
from biotope.croissant.biocypher_labels import escape_node_id
from biotope.croissant.mapping.model import (
    EntityMapping,
    ExplodeScan,
    Mapping,
    RelationMapping,
    Selector,
    to_sentence_case,
)
from biotope.croissant.mapping.scans import build_scan_operation
from biotope.croissant.mapping.selectors import resolve_selector


NodeTuple = tuple[str, str, dict[str, Any]]
# BioCypher edge tuple: (relationship_id, source_id, target_id, relationship_label, properties).
# `relationship_id` defaults to None (BioCypher auto-generates one); the 4-tuple shape
# (src, tgt, label, props) is also accepted for back-compat, but we emit the canonical
# 5-tuple so downstream code is unambiguous.
EdgeTuple = tuple[str | None, str, str, str, dict[str, Any]]


@dataclass
class CompileStats:
    """Row-level compile counters for nodes and edges."""

    emitted_nodes: int = 0
    emitted_edges: int = 0
    dropped_nodes_non_scalar: int = 0
    dropped_edges_non_scalar: int = 0
    deferred_relations: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "emitted_nodes": self.emitted_nodes,
            "emitted_edges": self.emitted_edges,
            "dropped_nodes_non_scalar": self.dropped_nodes_non_scalar,
            "dropped_edges_non_scalar": self.dropped_edges_non_scalar,
            "deferred_relations": self.deferred_relations,
        }


# ---------------------------------------------------------------------------
# Entity emission
# ---------------------------------------------------------------------------


def iter_entity_tuples(
    mapping: Mapping,
    context: AcquisitionContext,
    *,
    only_resolved: bool = False,
    stats: CompileStats | None = None,
) -> Iterator[NodeTuple]:
    """Yield ``(node_id, node_label, properties)`` for each declared entity.

    ``only_resolved=True`` silently skips unresolved entity slots — used by the
    preview engine so partial mappings still produce some output.
    """
    for name, entity in mapping.entities.items():
        if entity.is_empty():
            # Stub from intent capture; the slot is bound in another mapping.
            continue
        if not entity.is_resolved():
            if only_resolved:
                continue
            msg = f"Cannot compile unresolved entity `entities.{name}`"
            raise ValueError(msg)
        label = name
        scan_op = build_scan_operation(
            entity.scan,
            record_set=entity.record_set,  # type: ignore[arg-type]
            fields=_entity_fields(entity, mapping.ids),
            where=entity.where,
        )
        for ctx in scan_op.iter_contexts(context, ids=mapping.ids):
            node_id = resolve_selector(entity.id, ctx)  # type: ignore[arg-type]
            if not _is_scalar_id(node_id):
                if stats is not None:
                    stats.dropped_nodes_non_scalar += 1
                continue
            properties = {prop_name: resolve_selector(prop, ctx) for prop_name, prop in entity.properties.items()}
            if stats is not None:
                stats.emitted_nodes += 1
            yield (escape_node_id(str(node_id)), label, properties)


def iter_relation_tuples(
    mapping: Mapping,
    context: AcquisitionContext,
    *,
    only_resolved: bool = False,
    stats: CompileStats | None = None,
) -> Iterator[EdgeTuple]:
    """Yield ``(relationship_id, source_id, target_id, label, properties)`` per relation.

    ``relationship_id`` is ``None`` in v1 (BioCypher auto-generates one).
    """
    for name, relation in mapping.relations.items():
        if relation.is_empty():
            continue
        if relation.is_deferred():
            if stats is not None:
                stats.deferred_relations += 1
            continue
        if not relation.is_resolved():
            if only_resolved:
                continue
            msg = f"Cannot compile unresolved relation `relations.{name}`"
            raise ValueError(msg)
        label = name
        scan_op = build_scan_operation(
            relation.scan,
            record_set=relation.record_set,  # type: ignore[arg-type]
            fields=_relation_fields(relation, mapping.ids),
            where=relation.where,
        )
        for ctx in scan_op.iter_contexts(context, ids=mapping.ids):
            source_id = resolve_selector(relation.source.as_selector(), ctx)  # type: ignore[union-attr]
            target_id = resolve_selector(relation.target.as_selector(), ctx)  # type: ignore[union-attr]
            if not _is_scalar_id(source_id) or not _is_scalar_id(target_id):
                if stats is not None:
                    stats.dropped_edges_non_scalar += 1
                continue
            properties = {prop_name: resolve_selector(prop, ctx) for prop_name, prop in relation.properties.items()}
            if stats is not None:
                stats.emitted_edges += 1
            yield (
                None,
                escape_node_id(str(source_id)),
                escape_node_id(str(target_id)),
                label,
                properties,
            )


def _is_scalar_id(value: Any) -> bool:
    """Reject IDs that aren't scalar strings/numbers — lists / dicts produce garbage."""
    if value is None:
        return False
    return isinstance(value, str | int | float | bool)


def _entity_fields(entity: EntityMapping, ids: dict[str, Selector] | None = None) -> list[str] | None:
    """Compute the union of base fields referenced by ``entity``."""
    ids = ids or {}
    fields: set[str] = set()
    _add_selector_fields(entity.id, fields, ids)
    for prop in entity.properties.values():
        _add_selector_fields(prop, fields, ids)
    if isinstance(entity.scan, ExplodeScan):
        fields.update(entity.scan.axes.values())
    return _materialise_field_set(fields, entity.scan)


def _relation_fields(relation: RelationMapping, ids: dict[str, Selector] | None = None) -> list[str] | None:
    ids = ids or {}
    fields: set[str] = set()
    if relation.source is not None:
        _add_selector_fields(relation.source.as_selector(), fields, ids)
    if relation.target is not None:
        _add_selector_fields(relation.target.as_selector(), fields, ids)
    for prop in relation.properties.values():
        _add_selector_fields(prop, fields, ids)
    if isinstance(relation.scan, ExplodeScan):
        fields.update(relation.scan.axes.values())
    return _materialise_field_set(fields, relation.scan)


def _add_selector_fields(
    selector: Selector | None,
    out: set[str],
    ids: dict[str, Selector],
    seen: set[str] | None = None,
) -> None:
    """Collect base-row fields referenced by ``selector`` (skip explode-axis refs).

    Follows ``use:`` references against ``ids`` so a relation endpoint declared
    as ``use: <named_id>`` projects the underlying field into the DuckDB scan.
    A cycle guard keyed by id name keeps malformed mappings from looping.
    """
    if selector is None:
        return
    if selector.use is not None:
        seen = seen if seen is not None else set()
        if selector.use in seen or selector.use not in ids:
            return
        seen.add(selector.use)
        _add_selector_fields(ids[selector.use], out, ids, seen)
        return  # `use:` precludes `field:` on the same selector (model validation).
    if selector.transform == "hash_id":
        for f in selector.args.get("fields", []):
            if isinstance(f, str) and not f.startswith("$"):
                out.add(f)
        return
    if selector.field is not None and not selector.field.startswith("$"):
        out.add(selector.field)


def _materialise_field_set(fields: set[str], scan: Any) -> list[str] | None:
    if not fields:
        return None
    return sorted(fields)


# ---------------------------------------------------------------------------
# CompiledAdapter (BioCypher contract)
# ---------------------------------------------------------------------------


@dataclass
class CompiledAdapter:
    """A BioCypher-compatible adapter compiled from a :class:`Mapping`."""

    mapping: Mapping
    context: AcquisitionContext
    _compile_stats: CompileStats = field(default_factory=CompileStats, init=False, repr=False)
    _stats_computed: bool = field(default=False, init=False, repr=False)

    def get_nodes(self) -> Iterator[NodeTuple]:
        return iter_entity_tuples(self.mapping, self.context)

    def get_edges(self) -> Iterator[EdgeTuple]:
        return iter_relation_tuples(self.mapping, self.context)

    def compile_stats(self) -> CompileStats:
        """Return row-level drop/emission counters (single full scan, cached)."""
        if not self._stats_computed:
            stats = CompileStats()
            list(iter_entity_tuples(self.mapping, self.context, stats=stats))
            list(iter_relation_tuples(self.mapping, self.context, stats=stats))
            self._compile_stats = stats
            self._stats_computed = True
        return self._compile_stats


def compile_mapping(mapping: Mapping, context: AcquisitionContext) -> CompiledAdapter:
    """Compile ``mapping`` against ``context`` into a :class:`CompiledAdapter`."""
    mapping.assert_resolved()
    return CompiledAdapter(mapping=mapping, context=context)


# ---------------------------------------------------------------------------
# Schema helpers (used by materialize.py)
# ---------------------------------------------------------------------------


def derive_schema_term(name: str, declared: str | None) -> str:
    return declared if declared else to_sentence_case(name)


def derive_namespace(mapping: Mapping, entity: EntityMapping) -> str:
    """Derive the BioCypher namespace for an entity (explicit > as_curie prefix > "id")."""
    if entity.namespace is not None:
        return entity.namespace
    selector = entity.id
    while selector is not None:
        if selector.transform == "as_curie":
            prefix = selector.args.get("prefix")
            if isinstance(prefix, str):
                return prefix
            break
        if selector.use is not None and selector.use in mapping.ids:
            selector = mapping.ids[selector.use]
            continue
        break
    return "id"
