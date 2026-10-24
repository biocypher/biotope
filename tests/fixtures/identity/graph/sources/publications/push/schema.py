# This file is yours to edit; biotope never rewrites it. After a manifest change,
# review the drift biotope graph check explains, then update __source_digest__.
"""Typed records for one described record set; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class Push:
    __record_set__: ClassVar[str] = "push"
    __source_digest__: ClassVar[str] = "ccbca0d4b10bb16334bd128a4e26b4fed4b05b708f8021fed92c936d3a64742f"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    doi: str
    title: str
    orcid: str
    position: int | None = None
