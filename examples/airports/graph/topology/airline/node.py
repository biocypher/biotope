"""The airline node: one airline the desk's airline table lists."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, NewType


AirlineId = NewType("AirlineId", str)


def airline_id(code: str) -> AirlineId:
    """Mint an airline's graph identifier from its IATA airline code, as `airline:<code>`."""
    return AirlineId(f"airline:{code}")


@dataclass(frozen=True)
class Airline:
    """One airline `airlines.csv` lists, identified by its IATA airline code.

    `id` is `airline:<code>`; the local part is the code the airline table and the hub table both write, so an airline may be joined across those sources by that code.

    One node per airline. The notes name airlines in prose and those names are resolved to these codes by exact name, so an airline the notes name and the table lists are one node; a name the table does not list fails the build rather than becoming a second node.
    """

    schema_id: ClassVar[str] = "ops:airline"

    id: AirlineId
    name: str = field(metadata={"description": "The airline's full marketing name, as airlines.csv writes it."})
