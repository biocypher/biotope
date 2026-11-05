"""Reviewed people records; each attribute binds to the Croissant field of its name."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class People:
    """One row of raw/people.csv."""

    __record_set__: ClassVar[str] = "people"
    __source_digest__: ClassVar[str] = "a2026829e3b6d70677bfd324e118e0439ddb3bff9f1d64b53e911583570d6cf0"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    person_id: str
    name: str
