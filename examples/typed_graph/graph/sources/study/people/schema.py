"""Reviewed people records; each attribute binds to the Croissant field of its name."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class People:
    """One row of raw/people.csv."""

    __record_set__: ClassVar[str] = "people"
    __source_digest__: ClassVar[str] = "4bb9aea9c987aeb8d924ff9a2b2c889035f770d4fe3dff757615034f194640bd"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    person_id: str
    name: str
