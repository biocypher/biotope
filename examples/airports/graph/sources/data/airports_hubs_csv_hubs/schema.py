# This file is yours to edit; biotope rewrites only its IDs and digest when biotope mv moves its file.
# After any other manifest change, review the drift biotope graph check reports, then update __source_digest__.
"""Typed records for the hub table; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biotope.graph import source_field

from ....standardization import AIRLINE_CODE, AIRPORT_IATA


@dataclass(frozen=True, kw_only=True)
class HubRow:
    """One airline-airport pair this table states as a hub; it states no other role and no focus cities."""

    __record_set__: ClassVar[str] = "airports/hubs.csv#hubs"
    __source_digest__: ClassVar[str] = "3c104b9c885da03a696263b3ba87fc16293d3e34a7d604c9fbde114e40dbac7f"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    airport_iata: str = source_field("airport_iata", term=AIRPORT_IATA)
    airline_code: str = source_field("airline_code", term=AIRLINE_CODE)
