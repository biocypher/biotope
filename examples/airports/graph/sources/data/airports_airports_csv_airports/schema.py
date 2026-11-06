# This file is yours to edit; biotope rewrites only its IDs and digest when biotope mv moves its file.
# After any other manifest change, review the drift biotope graph check reports, then update __source_digest__.
"""Typed records for the airport table; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biotope.graph import source_field

from ....standardization import AIRPORT_IATA


@dataclass(frozen=True, kw_only=True)
class AirportRow:
    """One airport the operations desk works with. This table, not the notes, is the airport set."""

    __record_set__: ClassVar[str] = "airports/airports.csv#airports"
    __source_digest__: ClassVar[str] = "174d7f14291bb1f0d69b63618bcbf5166d7b7fe1bec3bc6fccaca88d903df8bb"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    airport_iata: str = source_field("iata", term=AIRPORT_IATA)
    name: str  # binds airports/airports.csv#airports/name by its own name
    city: str  # binds airports/airports.csv#airports/city by its own name
    country: str  # binds airports/airports.csv#airports/country by its own name
