"""Build unresolved semantic mapping scaffolds from project intent.

This module is deliberately heuristic-free. It only produces empty slot keys
from ``project.yaml``'s ``required_entities`` / ``required_relations`` lists,
normalising them to ``snake_case``. All semantic decisions — which record set,
which fields, which transforms — are left to the human or copilot agent.
"""

from __future__ import annotations

from collections.abc import Iterable

from biotope.croissant.mapping.model import (
    EntityMapping,
    Mapping,
    RelationMapping,
    to_snake_case,
)


def unresolved_scaffold(
    croissant_path: str,
    *,
    required_entities: Iterable[str] = (),
    required_relations: Iterable[str] = (),
) -> Mapping:
    """Return a :class:`Mapping` whose slots are unresolved placeholders.

    Original phrasing (the input strings) is *not* embedded in the slot keys —
    keys are mechanically normalised to ``snake_case``. Callers wishing to
    preserve the original phrasing should pass it through the renderer as an
    ``intent_comment``.
    """
    entities: dict[str, EntityMapping] = {}
    for name in required_entities:
        key = to_snake_case(name)
        entities[key] = EntityMapping()

    relations: dict[str, RelationMapping] = {}
    for name in required_relations:
        key = to_snake_case(name)
        relations[key] = RelationMapping()

    return Mapping(croissant=croissant_path, entities=entities, relations=relations)


def intent_comment(
    *,
    required_entities: Iterable[str] = (),
    required_relations: Iterable[str] = (),
    purpose: str | None = None,
) -> str:
    """Return a comment block preserving the human phrasing of declared intent."""
    lines = ["Intent captured from project.yaml:"]
    if purpose:
        lines.append(f"- purpose: {purpose}")
    entities = list(required_entities)
    relations = list(required_relations)
    if entities:
        lines.append("- entities:")
        for raw in entities:
            lines.append(f"  - {raw}  ->  {to_snake_case(raw)}")
    if relations:
        lines.append("- relations:")
        for raw in relations:
            lines.append(f"  - {raw}  ->  {to_snake_case(raw)}")
    if not entities and not relations:
        lines.append("- no entities or relations declared yet")
        lines.append("  (run `biotope map --entity <name> --relation <name>` or open the wizard)")
    return "\n".join(lines)
