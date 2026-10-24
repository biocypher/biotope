# This file is yours to edit; biotope never rewrites it. After a manifest change,
# review the drift biotope graph check explains, then update __source_digest__.
"""Typed records for one described record set; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class Directory:
    __record_set__: ClassVar[str] = "directory"
    __source_digest__: ClassVar[str] = "e24d68ea2d709c6fe6c6cf4f8b79eeff3465833c953c9f0609796f437905c623"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    upn: str
    name: str
    roster: str | None = None
