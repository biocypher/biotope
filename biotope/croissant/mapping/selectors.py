"""Runtime selector resolver and value-level transforms.

The data model in :mod:`biotope.croissant.mapping.model` describes selectors
declaratively. This module turns them into values at compile time.

Resolution path:

* ``use: <name>`` — look up a named entry in the mapping's ``ids`` table and
  resolve that selector instead.
* ``field: <name>`` — read ``name`` from the current :class:`RecordRow`. The
  special prefix ``$item`` refers to the current element when a scan is an
  explode scan; ``$item.foo`` looks up ``foo`` on the current element (when the
  element is a dict).
* ``transform`` — apply a named value-level transform to the extracted value.

Only ``passthrough``, ``as_curie``, and ``hash_id`` are exposed in v1. The
registry below is the only place new transforms get plugged in.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from biotope.croissant.acquisition.context import RecordRow
from biotope.croissant.mapping.model import Selector


@dataclass
class ResolutionContext:
    """Per-row evaluation context for selector resolution.

    For explode scans, ``items`` maps each axis name to its current element
    (Cartesian product across axes when multiple are declared). The legacy
    single-axis form lives under axis name ``"item"`` and is also surfaced as
    the ``item`` property for backwards compatibility.
    """

    row: RecordRow
    items: dict[str, Any] | None = None
    """Mapping of explode-axis name → current element value. ``None`` for row scans."""
    ids: Mapping[str, Selector] | None = None
    """Named reusable selectors (``ids:`` block of the mapping)."""

    @property
    def item(self) -> Any:
        """Backwards-compatible alias for ``items['item']`` under single-axis explode."""
        if self.items is None:
            return None
        return self.items.get("item")


def resolve_selector(selector: Selector, ctx: ResolutionContext) -> Any:
    """Resolve a :class:`Selector` against ``ctx`` and return the resulting value."""
    if selector.use is not None:
        if ctx.ids is None or selector.use not in ctx.ids:
            msg = f"Named id {selector.use!r} not defined in mapping ids"
            raise KeyError(msg)
        return resolve_selector(ctx.ids[selector.use], ctx)

    if selector.transform == "hash_id":
        return _apply_hash_id(selector.args, ctx)

    if selector.field is None:
        return None

    value = _extract_value(selector.field, ctx)
    return _apply_value_transform(selector.transform, selector.args, value)


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------

def _extract_value(field: str, ctx: ResolutionContext) -> Any:
    if field.startswith("$"):
        axis, _, subpath = field[1:].partition(".")
        items = ctx.items or {}
        if axis not in items:
            return None
        value = items[axis]
        if not subpath:
            return value
        return _walk_path(value, subpath)
    return ctx.row.get(field)


def _walk_path(obj: Any, path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(part)
        elif hasattr(cur, part):
            cur = getattr(cur, part)
        else:
            return None
    return cur


# ---------------------------------------------------------------------------
# Value-level transforms
# ---------------------------------------------------------------------------


ValueTransform = Callable[[Any, dict[str, Any]], Any]


def _passthrough(value: Any, args: dict[str, Any]) -> Any:
    return value


def _as_curie(value: Any, args: dict[str, Any]) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, list | tuple | dict):
        # Refuse to build a CURIE from a structured value — produces garbage strings
        # like "ensembl:['x','y']". The mapping needs `scan: {explode: <field>}`
        # to project the array into one row per element.
        return None
    prefix = args.get("prefix")
    if prefix is None:
        msg = "as_curie requires args.prefix"
        raise ValueError(msg)
    separator = args.get("separator", ":")
    return f"{prefix}{separator}{value}"


_VALUE_TRANSFORMS: dict[str, ValueTransform] = {
    "passthrough": _passthrough,
    "as_curie": _as_curie,
}


def _apply_value_transform(name: str, args: dict[str, Any], value: Any) -> Any:
    transform = _VALUE_TRANSFORMS.get(name)
    if transform is None:
        msg = f"Unknown transform {name!r}; available: {sorted(_VALUE_TRANSFORMS) + ['hash_id']}"
        raise KeyError(msg)
    return transform(value, args)


def _apply_hash_id(args: dict[str, Any], ctx: ResolutionContext) -> str | None:
    """Stable SHA-256 over an ordered tuple of fields.

    ``args.fields`` lists the source fields (resolved against the current row /
    ``$item`` per the same rules as :func:`_extract_value`). Missing values
    short-circuit to ``None`` so the build skips emitting the entity/relation.
    """
    fields = args.get("fields")
    if not fields:
        msg = "hash_id requires args.fields (list of field names)"
        raise ValueError(msg)
    parts: list[str] = []
    for field_name in fields:
        value = _extract_value(field_name, ctx)
        if value is None:
            return None
        parts.append(str(value))

    prefix = args.get("prefix")
    length = args.get("length", 16)
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:length]
    return f"{prefix}:{digest}" if prefix else digest


def available_transforms() -> tuple[str, ...]:
    """Return the names of built-in transforms exposed in v1."""
    return ("passthrough", "as_curie", "hash_id")
