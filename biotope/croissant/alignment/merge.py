"""Combine multiple compiled adapters via an :class:`Alignment`.

For v1 only :class:`EquivalenceKind.SAME_NODE` is implemented. The merge is
deliberately simple: we rewrite the IDs emitted by adapter B's matching entity
type so they collide with adapter A's IDs on the same join key. BioCypher
then naturally deduplicates the resulting node tuples.

After the IR shift to semantic entities/relations, ``Reference.node_type`` is
matched against entity *keys* (= generated input labels) rather than legacy
``node.type`` strings.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from biotope.croissant.alignment.model import Alignment, EquivalenceKind
from biotope.croissant.mapping.compile import CompiledAdapter, EdgeTuple, NodeTuple


@dataclass
class MergedAdapter:
    """A BioCypher-compatible adapter that streams from several compiled adapters."""

    adapters_by_stem: dict[str, CompiledAdapter]
    alignment: Alignment

    def get_nodes(self) -> Iterator[NodeTuple]:
        rewrites = self._build_node_id_rewrites()
        for stem, adapter in self.adapters_by_stem.items():
            for node_id, label, props in adapter.get_nodes():
                key = (stem, label)
                if key in rewrites:
                    join_field, canonical_prefix = rewrites[key]
                    join_value = props.get(join_field)
                    if join_value is not None:
                        node_id = f"{canonical_prefix}:{join_value}"
                yield (node_id, label, props)

    def get_edges(self) -> Iterator[EdgeTuple]:
        for adapter in self.adapters_by_stem.values():
            yield from adapter.get_edges()

    def _build_node_id_rewrites(self) -> dict[tuple[str, str], tuple[str, str]]:
        """Build ``{(mapping_stem, entity_key): (join_field, prefix)}``.

        ``Reference.node_type`` now identifies an entity by its mapping key.
        """
        result: dict[tuple[str, str], tuple[str, str]] = {}
        for eq in self.alignment.equivalences:
            if eq.kind != EquivalenceKind.SAME_NODE:
                continue
            a_adapter = self.adapters_by_stem.get(eq.a.mapping)
            if a_adapter is None:
                continue
            prefix = self._infer_curie_prefix(a_adapter, eq.a.node_type) or eq.a.node_type
            result[(eq.b.mapping, eq.b.node_type)] = (eq.join_on.b, prefix)
        return result

    @staticmethod
    def _infer_curie_prefix(adapter: CompiledAdapter, entity_key: str) -> str | None:
        """Best-effort: read ``args.prefix`` from the matching entity's id selector."""
        entity = adapter.mapping.entities.get(entity_key)
        if entity is None or entity.id is None:
            return None
        selector = entity.id
        ids = adapter.mapping.ids
        while selector is not None:
            if selector.transform == "as_curie":
                prefix = selector.args.get("prefix")
                if isinstance(prefix, str):
                    return prefix
                return None
            if selector.use is not None and selector.use in ids:
                selector = ids[selector.use]
                continue
            return None
        return None


def merge_adapters(
    adapters: dict[str, CompiledAdapter],
    alignment: Alignment,
) -> MergedAdapter:
    """Build a :class:`MergedAdapter` from a stem→adapter map and an alignment."""
    return MergedAdapter(adapters_by_stem=adapters, alignment=alignment)
