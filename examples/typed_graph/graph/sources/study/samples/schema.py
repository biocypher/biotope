"""Reviewed sample records; each attribute binds to the Croissant field of its name."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class Samples:
    """One row of raw/samples.csv."""

    __record_set__: ClassVar[str] = "samples"
    __source_digest__: ClassVar[str] = "232b786019f89a6fdab63b0e75cf3af27c85d43ca509b13a94b0d5e460670b91"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    sample_id: str
    person_id: str
    tissue: str
    score: float
