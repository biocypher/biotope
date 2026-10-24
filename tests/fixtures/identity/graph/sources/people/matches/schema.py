# This file is yours to edit; biotope never rewrites it. After a manifest change,
# review the drift biotope graph check explains, then update __source_digest__.
"""Typed records for one described record set; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class Matches:
    __record_set__: ClassVar[str] = "matches"
    __source_digest__: ClassVar[str] = "82aa4224166fe3fb9068a408fc1be754f72e73a69428f3e0faed58ef63f1bdab"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    subject_id: str
    predicate_id: str
    object_id: str
    mapping_justification: str
    confidence: float | None = None
