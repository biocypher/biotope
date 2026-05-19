"""Combine multiple compiled adapters via an :class:`Alignment`.

For v1 only :class:`EquivalenceKind.SAME_NODE` is implemented. The merge is
deliberately simple: we rewrite the IDs emitted by adapter B's matching node
type so they collide with adapter A's IDs on the same join key. BioCypher
then naturally deduplicates the resulting node tuples.

A richer ER backend can plug into this same surface by inserting a
``rewrite_id`` step at the SAME_NODE branch.
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
        """Yield deduplicated nodes from every adapter under the alignment."""
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
        """Yield edges from every adapter.

        v1 caveat: endpoint rewriting only applies through node-side ID
        collapse. Edges whose source/target are already CURIE-shaped will
        collide naturally with the rewritten nodes. Edges with synthetic
        endpoint IDs require an extension here.
        """
        for adapter in self.adapters_by_stem.values():
            yield from adapter.get_edges()

    def _build_node_id_rewrites(self) -> dict[tuple[str, str], tuple[str, str]]:
        """Build a ``{(mapping_stem, node_type): (join_field, prefix)}`` table.

        For each ``same_node`` equivalence, side B's node IDs are rewritten to
        use side A's CURIE prefix on the join value. Side A is left as-is.
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
    def _infer_curie_prefix(adapter: CompiledAdapter, node_type: str) -> str | None:
        """Best-effort: read the ``prefix`` from the matching node's id transform."""
        for node in adapter.mapping.nodes:
            if node.type == node_type and node.id.transform == "as_curie":
                prefix = node.id.args.get("prefix")
                if isinstance(prefix, str):
                    return prefix
        return None


def merge_adapters(
    adapters: dict[str, CompiledAdapter],
    alignment: Alignment,
) -> MergedAdapter:
    """Build a :class:`MergedAdapter` from a stem→adapter map and an alignment."""
    return MergedAdapter(adapters_by_stem=adapters, alignment=alignment)
