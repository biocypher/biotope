"""The airport node: one airport the desk's airport table describes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, NewType


AirportId = NewType("AirportId", str)


def airport_id(iata: str) -> AirportId:
    """Mint an airport's graph identifier from its IATA code, as `airport:<IATA>`."""
    return AirportId(f"airport:{iata}")


@dataclass(frozen=True)
class Airport:
    """One airport `airports.csv` describes, identified by its IATA code.

    `id` is `airport:<IATA>`; the local part is the code the airport table, the hub table and the notes all write, so an airport may be joined across those sources by that code.

    The node set is the airport table's, not the notes': the notes are not a complete inventory, so an airport absent from the graph is one no source here describes, not one the desk does not work with.
    """

    schema_id: ClassVar[str] = "ops:airport"

    id: AirportId
    name: str = field(metadata={"description": "The airport's full name, as airports.csv writes it."})
    city: str = field(metadata={"description": "The city the airport serves, as airports.csv names it."})
    country: str = field(
        metadata={"description": "ISO 3166-1 alpha-2 country code of the airport, as airports.csv writes it."}
    )
