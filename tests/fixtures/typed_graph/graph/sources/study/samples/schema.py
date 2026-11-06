"""Reviewed sample records; each attribute binds to the Croissant field of its name."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class Samples:
    """One row of raw/samples.csv."""

    __record_set__: ClassVar[str] = "samples"
    __source_digest__: ClassVar[str] = "73a5e23963bfca71e009020ed4c01649671ddfdaf3eb3c66870cc28e6d8d5fb8"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    sample_id: str
    person_id: str
    tissue: str
    score: float
