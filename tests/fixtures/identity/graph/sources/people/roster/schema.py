# This file is yours to edit; biotope never rewrites it. After a manifest change,
# review the drift biotope graph check explains, then update __source_digest__.
"""Typed records for one described record set; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class Roster:
    __record_set__: ClassVar[str] = "roster"
    __source_digest__: ClassVar[str] = "89fd9696b073a3c9385d759467dfb4daeda08be806cc21c4a30be7c6ef1d9bfa"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    record: str
    name: str
    email: str | None = None
    orcid: str | None = None
