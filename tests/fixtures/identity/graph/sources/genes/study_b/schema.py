# This file is yours to edit; biotope never rewrites it. After a manifest change,
# review the drift biotope graph check explains, then update __source_digest__.
"""Typed records for one described record set; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class StudyB:
    __record_set__: ClassVar[str] = "study_b"
    __source_digest__: ClassVar[str] = "515f8c392910ce026b14da9c8270c7da38dc515b143e507a0bc3534edec844f2"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    row: int
    ensembl: str | None = None
    symbol: str
