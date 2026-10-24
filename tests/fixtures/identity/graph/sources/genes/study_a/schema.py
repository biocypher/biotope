# This file is yours to edit; biotope never rewrites it. After a manifest change,
# review the drift biotope graph check explains, then update __source_digest__.
"""Typed records for one described record set; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class StudyA:
    __record_set__: ClassVar[str] = "study_a"
    __source_digest__: ClassVar[str] = "4227cb2740d9f310098613493581732053dc16044394d1f30e7b616b5558c17b"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    row: int
    ensembl: str | None = None
    symbol: str
