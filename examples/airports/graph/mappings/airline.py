"""Airline nodes: one per airline the airline table lists."""

from __future__ import annotations

from collections.abc import Iterator

from biotope.graph import Mapping, SourceRecord

from ..alignment.airlines import AirlineIdentity
from ..topology.airline.node import Airline, airline_id


def make_airline(identity: SourceRecord[AirlineIdentity]) -> Iterator[Airline]:
    """Emit the airline node for one row of airlines.csv."""
    value = identity.value
    yield Airline(id=airline_id(value.airline_code), name=value.airline_name)


AIRLINES = Mapping(
    name="ops:airline",
    function=make_airline,
    evidence=(
        "Every airline airlines.csv lists. One node per airline: the names the notes use are resolved to "
        "these codes by exact name, so the notes add no node of their own.",
    ),
)
