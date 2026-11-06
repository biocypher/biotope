# This file is yours to edit; biotope rewrites only its IDs and digest when biotope mv moves its file.
# After any other manifest change, review the drift biotope graph check reports, then update __source_digest__.
"""Typed records for the airline table; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biotope.graph import source_field

from ....standardization import AIRLINE_CODE, AIRLINE_NAME


@dataclass(frozen=True, kw_only=True)
class AirlineRow:
    """One airline the operations desk tracks. This table, not the notes, is the airline set."""

    __record_set__: ClassVar[str] = "airports/airlines.csv#airlines"
    __source_digest__: ClassVar[str] = "0885daa08f95779a3aca697dc88a3b3ac112a5da520fc830a0834b99bbb3298f"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    airline_code: str = source_field("code", term=AIRLINE_CODE)
    airline_name: str = source_field("name", term=AIRLINE_NAME)
