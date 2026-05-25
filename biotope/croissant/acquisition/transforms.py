"""Minimal value transforms used by the mapping compiler.

A :class:`Transform` is a pure callable from one :class:`RecordRow` to a value.
This module provides the three transforms that cover ~80% of real mappings:

* :func:`passthrough` — return a field value as-is
* :func:`as_curie` — prefix a field value to form a CURIE (e.g. ``ensembl:ENSG…``)
* :func:`hash_id` — stable SHA-256 hash over an ordered tuple of fields

More transforms can be added without changing this signature.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from biotope.croissant.acquisition.context import RecordRow


Transform = Callable[[RecordRow], Any]


def passthrough(field: str) -> Transform:
    """Return the value of ``field`` from each row."""

    def _t(row: RecordRow) -> Any:
        return row.get(field)

    return _t


def as_curie(prefix: str, field: str, *, separator: str = ":") -> Transform:
    """Return ``"<prefix><separator><field_value>"`` per row.

    Returns ``None`` for rows where the field is missing or empty so the build
    can skip the resulting node/edge instead of emitting a malformed CURIE.
    """

    def _t(row: RecordRow) -> str | None:
        value = row.get(field)
        if value is None or value == "":
            return None
        return f"{prefix}{separator}{value}"

    return _t


def hash_id(*fields: str, prefix: str | None = None, length: int = 16) -> Transform:
    """Return a stable hash over ``fields`` (in order).

    Useful for synthetic IDs on records that lack a natural primary key.
    """

    def _t(row: RecordRow) -> str | None:
        parts: list[str] = []
        for f in fields:
            v = row.get(f)
            if v is None:
                return None
            parts.append(str(v))
        digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:length]
        return f"{prefix}:{digest}" if prefix else digest

    return _t


def compose(*transforms: Transform) -> Transform:
    """Return a transform that applies ``transforms`` left-to-right.

    The output of each transform becomes the input of the next, wrapped in a
    one-key :class:`RecordRow` under the name ``"_"`` so downstream transforms
    can reference it as ``passthrough("_")``. Mostly useful for testing.
    """

    def _t(row: RecordRow) -> Any:
        value: Any = row
        for tr in transforms:
            if isinstance(value, RecordRow):
                value = tr(value)
            else:
                value = tr(RecordRow(record_set=row.record_set, values={"_": value}))
        return value

    return _t


_RESOLVERS: dict[str, Callable[..., Transform]] = {
    "passthrough": passthrough,
    "as_curie": as_curie,
    "hash_id": hash_id,
}


def resolve_transform(name: str, /, **kwargs: Any) -> Transform:
    """Look up a transform by name and bind ``kwargs``.

    Used by the mapping compiler so YAML-declared transforms can be turned
    into callables without an ``eval``.
    """
    if name not in _RESOLVERS:
        msg = f"Unknown transform {name!r}; available: {sorted(_RESOLVERS)}"
        raise KeyError(msg)
    return _RESOLVERS[name](**kwargs)
