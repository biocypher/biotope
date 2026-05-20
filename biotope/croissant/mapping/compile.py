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
from dataclasses import dataclass
from typing import Any

from biotope.croissant.acquisition.context import AcquisitionContext
from biotope.croissant.mapping.model import (
    EntityMapping,
    ExplodeScan,
    Mapping,
    RelationMapping,
    RowScan,
    Selector,
    to_sentence_case,
)
from biotope.croissant.mapping.scans import build_scan_operation
from biotope.croissant.mapping.selectors import ResolutionContext, resolve_selector

NodeTuple = tuple[str, str, dict[str, Any]]
EdgeTuple = tuple[str, str, str, str, dict[str, Any]]


# ---------------------------------------------------------------------------
# Entity emission
# ---------------------------------------------------------------------------


def iter_entity_tuples(
    mapping: Mapping,
    context: AcquisitionContext,
    *,
    only_resolved: bool = False,
) -> Iterator[NodeTuple]:
    """Yield ``(node_id, node_label, properties)`` for each declared entity.

    ``only_resolved=True`` silently skips unresolved entity slots — used by the
    preview engine so partial mappings still produce some output.
    """
    for name, entity in mapping.entities.items():
        if not entity.is_resolved():
            if only_resolved:
                continue
            msg = f"Cannot compile unresolved entity `entities.{name}`"
            raise ValueError(msg)
        label = name
        scan_op = build_scan_operation(
            entity.scan,
            record_set=entity.record_set,  # type: ignore[arg-type]
            fields=_entity_fields(entity),
            where=entity.where,
        )
        for ctx in scan_op.iter_contexts(context, ids=mapping.ids):
            node_id = resolve_selector(entity.id, ctx)  # type: ignore[arg-type]
            if node_id is None:
                continue
            properties = {
                prop_name: resolve_selector(prop, ctx)
                for prop_name, prop in entity.properties.items()
            }
            yield (str(node_id), label, properties)


def iter_relation_tuples(
    mapping: Mapping,
    context: AcquisitionContext,
    *,
    only_resolved: bool = False,
) -> Iterator[EdgeTuple]:
    """Yield ``(source_id, target_id, label, type, properties)`` per relation."""
    for name, relation in mapping.relations.items():
        if not relation.is_resolved():
            if only_resolved:
                continue
            msg = f"Cannot compile unresolved relation `relations.{name}`"
            raise ValueError(msg)
        label = name
        scan_op = build_scan_operation(
            relation.scan,
            record_set=relation.record_set,  # type: ignore[arg-type]
            fields=_relation_fields(relation),
            where=relation.where,
        )
        for ctx in scan_op.iter_contexts(context, ids=mapping.ids):
            source_id = resolve_selector(relation.source.as_selector(), ctx)  # type: ignore[union-attr]
            target_id = resolve_selector(relation.target.as_selector(), ctx)  # type: ignore[union-attr]
            if source_id is None or target_id is None:
                continue
            properties = {
                prop_name: resolve_selector(prop, ctx)
                for prop_name, prop in relation.properties.items()
            }
            yield (str(source_id), str(target_id), label, label, properties)


def _entity_fields(entity: EntityMapping) -> list[str] | None:
    """Compute the union of base fields referenced by ``entity``."""
    fields: set[str] = set()
    _add_selector_fields(entity.id, fields)
    for prop in entity.properties.values():
        _add_selector_fields(prop, fields)
    if isinstance(entity.scan, ExplodeScan):
        fields.add(entity.scan.explode)
    return _materialise_field_set(fields, entity.scan)


def _relation_fields(relation: RelationMapping) -> list[str] | None:
    fields: set[str] = set()
    if relation.source is not None:
        _add_selector_fields(relation.source.as_selector(), fields)
    if relation.target is not None:
        _add_selector_fields(relation.target.as_selector(), fields)
    for prop in relation.properties.values():
        _add_selector_fields(prop, fields)
    if isinstance(relation.scan, ExplodeScan):
        fields.add(relation.scan.explode)
    return _materialise_field_set(fields, relation.scan)


def _add_selector_fields(selector: Selector | None, out: set[str]) -> None:
    if selector is None:
        return
    if selector.transform == "hash_id":
        for f in selector.args.get("fields", []):
            if isinstance(f, str) and not f.startswith("$item"):
                out.add(f)
        return
    if selector.field is not None and not selector.field.startswith("$item"):
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

    def get_nodes(self) -> Iterator[NodeTuple]:
        return iter_entity_tuples(self.mapping, self.context)

    def get_edges(self) -> Iterator[EdgeTuple]:
        return iter_relation_tuples(self.mapping, self.context)


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
