"""Render semantic ``mapping.yaml`` documents with optional inspector appendix.

The renderer never autoselects record sets or fields. It writes the mapping
literally and (optionally) appends a comment block summarising the referenced
Croissant dataset so an editor — human or copilot — can resolve slots without
re-running inspection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from biotope.croissant.mapping.model import (
    EntityMapping,
    ExplodeScan,
    Mapping,
    RelationMapping,
    RowScan,
    Scan,
    Selector,
)
from biotope.croissant.spec import CroissantDatasetModel


def render_mapping_yaml(mapping: Mapping) -> str:
    """Serialise a :class:`Mapping` as plain YAML, omitting noise defaults."""
    payload = _mapping_payload(mapping)
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def render_mapping_with_appendix(
    mapping: Mapping,
    *,
    appendix: str | None = None,
    intent_comment: str | None = None,
) -> str:
    """Render ``mapping`` YAML, optionally followed by an inspector comment appendix.

    ``intent_comment`` is rendered as a top-of-file comment block (typically the
    original human phrasing of declared entities/relations from ``project.yaml``).
    ``appendix`` is appended verbatim as a YAML comment block at the end of the
    document.
    """
    sections: list[str] = []
    if intent_comment:
        sections.append(_as_comment_block(intent_comment))
    sections.append(render_mapping_yaml(mapping))
    if appendix:
        sections.append(_as_comment_block(appendix))
    return "\n".join(s.rstrip() for s in sections) + "\n"


def _mapping_payload(mapping: Mapping) -> dict[str, Any]:
    out: dict[str, Any] = {"croissant": mapping.croissant}
    if mapping.ids:
        out["ids"] = {name: _selector_payload(sel) for name, sel in mapping.ids.items()}
    if mapping.entities:
        out["entities"] = {name: _entity_payload(entity) for name, entity in mapping.entities.items()}
    if mapping.relations:
        out["relations"] = {name: _relation_payload(rel) for name, rel in mapping.relations.items()}
    return out


def _entity_payload(entity: EntityMapping) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if entity.record_set is not None:
        out["record_set"] = entity.record_set
    out["scan"] = _scan_payload(entity.scan)
    if entity.schema_term is not None:
        out["schema_term"] = entity.schema_term
    if entity.namespace is not None:
        out["namespace"] = entity.namespace
    if entity.id is not None:
        out["id"] = _selector_payload(entity.id)
    if entity.properties:
        out["properties"] = {k: _selector_payload(v) for k, v in entity.properties.items()}
    if entity.where is not None:
        out["where"] = entity.where
    return out


def _relation_payload(relation: RelationMapping) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if relation.record_set is not None:
        out["record_set"] = relation.record_set
    out["scan"] = _scan_payload(relation.scan)
    if relation.schema_term is not None:
        out["schema_term"] = relation.schema_term
    if relation.source is not None:
        out["source"] = _endpoint_payload(relation.source)
    if relation.target is not None:
        out["target"] = _endpoint_payload(relation.target)
    if relation.properties:
        out["properties"] = {k: _selector_payload(v) for k, v in relation.properties.items()}
    if relation.where is not None:
        out["where"] = relation.where
    return out


def _selector_payload(sel: Selector) -> Any:
    if sel.transform == "passthrough" and not sel.args and sel.use is None and sel.field is not None:
        return sel.field
    return _strip_defaults(
        {
            "field": sel.field,
            "use": sel.use,
            "transform": sel.transform if sel.transform != "passthrough" else None,
            "args": sel.args or None,
        }
    )


def _endpoint_payload(endpoint: Any) -> Any:
    return _strip_defaults(
        {
            "entity": endpoint.entity,
            "field": endpoint.field,
            "use": endpoint.use,
            "transform": endpoint.transform if endpoint.transform != "passthrough" else None,
            "args": endpoint.args or None,
        }
    )


def _scan_payload(scan: Scan) -> Any:
    if isinstance(scan, RowScan):
        return "row"
    if isinstance(scan, ExplodeScan):
        # Single-axis form sugars back to a bare string so YAML stays compact.
        if list(scan.axes.keys()) == ["item"]:
            return {"explode": scan.axes["item"]}
        return {"explode": dict(scan.axes)}
    return scan  # pragma: no cover


def _strip_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if v is not None}


def _as_comment_block(text: str) -> str:
    lines = text.splitlines() or [""]
    return "\n".join(f"# {line}" if line else "#" for line in lines) + "\n"


def build_inspector_appendix(
    dataset: CroissantDatasetModel,
    *,
    datasets_location: str | Path | None = None,
    preview_rows: int = 3,
) -> str:
    """Build the inspector comment appendix for a Croissant dataset.

    Defers to :mod:`biotope.croissant.mapping.inspector` so the same logic
    powers ``map inspect``, ``map scaffold``, and the wizard preview.
    """
    from biotope.croissant.mapping.inspector import render_inspector_text

    return render_inspector_text(
        dataset,
        datasets_location=datasets_location,
        preview_rows=preview_rows,
    )
