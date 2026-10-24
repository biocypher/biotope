# This file is yours to edit; biotope never rewrites it. After a manifest change,
# review the drift biotope graph check explains, then update __source_digest__.
"""Typed records for one described record set; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class Openalex:
    __record_set__: ClassVar[str] = "openalex"
    __source_digest__: ClassVar[str] = "4ed519f32e5b07800ec71cddf0cc02fe541f3bd243d206e9c0f985904e4a1cea"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    doi: str
    title: str
    orcid: str
    position: int | None = None
