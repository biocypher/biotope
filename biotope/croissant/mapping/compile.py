"""Compile a :class:`Mapping` into a BioCypher-compatible adapter object.

The compiled adapter exposes ``get_nodes()`` and ``get_edges()`` generators
that yield the tuples BioCypher's ``write_nodes`` / ``write_edges`` expect:

* nodes: ``(node_id, node_label, properties_dict)``
* edges: ``(source_id, target_id, edge_label, edge_type, properties_dict)``

No part of this module imports BioCypher itself — the contract is structural,
matching the protocol BioCypher already accepts.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from biotope.croissant.acquisition.context import AcquisitionContext
from biotope.croissant.acquisition.transforms import Transform, hash_id, passthrough, resolve_transform
from biotope.croissant.mapping.model import EndpointMapping, Mapping

NodeTuple = tuple[str, str, dict[str, Any]]
EdgeTuple = tuple[str, str, str, str, dict[str, Any]]


def _build_transform(endpoint: EndpointMapping) -> Transform:
    """Resolve an :class:`EndpointMapping` to a callable transform."""
    name = endpoint.transform
    kwargs = dict(endpoint.args)

    if name == "passthrough":
        return passthrough(endpoint.from_)
    if name == "hash_id":
        fields = kwargs.pop("fields", None) or [endpoint.from_]
        return hash_id(*fields, **kwargs)
    kwargs.setdefault("field", endpoint.from_)
    return resolve_transform(name, **kwargs)


@dataclass
class CompiledAdapter:
    """A BioCypher-compatible adapter compiled from a :class:`Mapping`."""

    mapping: Mapping
    context: AcquisitionContext

    def get_nodes(self) -> Iterator[NodeTuple]:
        """Yield ``(node_id, node_label, properties)`` tuples."""
        for node in self.mapping.nodes:
            id_fn = _build_transform(node.id)
            fields = [node.id.from_, *node.properties]
            for row in self.context.stream(node.record_set, fields=fields, where=node.where):
                node_id = id_fn(row)
                if node_id is None:
                    continue
                props = {p: row.get(p) for p in node.properties}
                yield (str(node_id), node.type, props)

    def get_edges(self) -> Iterator[EdgeTuple]:
        """Yield ``(source_id, target_id, label, type, properties)`` tuples."""
        for edge in self.mapping.edges:
            src_fn = _build_transform(edge.source)
            tgt_fn = _build_transform(edge.target)
            referenced = {edge.source.from_, edge.target.from_, *edge.properties}
            for row in self.context.stream(edge.record_set, fields=list(referenced), where=edge.where):
                src = src_fn(row)
                tgt = tgt_fn(row)
                if src is None or tgt is None:
                    continue
                props = {p: row.get(p) for p in edge.properties}
                yield (str(src), str(tgt), edge.type, edge.type, props)


def compile_mapping(mapping: Mapping, context: AcquisitionContext) -> CompiledAdapter:
    """Compile ``mapping`` against ``context`` into a :class:`CompiledAdapter`."""
    return CompiledAdapter(mapping=mapping, context=context)
