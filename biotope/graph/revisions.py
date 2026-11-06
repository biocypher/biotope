from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from biotope.graph.sources import FieldNode, walk_fields


VALUE_LIMIT = 80


def project_root(path: Path) -> Path | None:
    """The nearest ancestor of a path that holds ``.biotope/``, if it is inside a Biotope project."""
    return next((parent for parent in path.resolve().parents if (parent / ".biotope").is_dir()), None)


def short_revision(revision: str | None) -> str:
    return (revision or "none")[:12]


def _value(value: object) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return text if len(text) <= VALUE_LIMIT else text[: VALUE_LIMIT - 1] + "…"


def _fields(definition: dict[str, Any]) -> dict[str, FieldNode] | None:
    """A RecordSet definition's fields by identity, or None for a file definition."""
    records = definition.get("recordSet")
    if not isinstance(records, list) or len(cast(list[object], records)) != 1:
        return None
    record = cast(list[object], records)[0]
    if not isinstance(record, dict):
        return None
    typed = cast(dict[str, Any], record)
    return {node.identity: node for node in walk_fields(typed, str(typed.get("@id", "/recordSet/0")))}


def describe_contract(definition: dict[str, Any]) -> list[str]:
    fields = _fields(definition)
    if fields is not None:
        lines = [
            f"{identity}: {node.item.get('dataType', 'no dataType')}" + ("" if node.nullable else ", not nullable")
            for identity, node in fields.items()
        ]
        key = cast(dict[str, Any], definition["recordSet"][0]).get("key")
        return lines if key is None else [*lines, f"key: {_value(key)}"]
    resource = definition.get("distribution")
    if isinstance(resource, dict):
        typed = cast(dict[str, Any], resource)
        return [f"{key}: {_value(typed[key])}" for key in ("contentUrl", "includes", "encodingFormat") if key in typed]
    return []
