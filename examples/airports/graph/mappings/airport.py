"""Airport nodes: one per airport the airport table describes."""

from __future__ import annotations

from collections.abc import Iterator

from biotope.graph import Mapping, SourceRecord

from ..alignment.airports import AirportIdentity
from ..topology.airport.node import Airport, airport_id


def make_airport(identity: SourceRecord[AirportIdentity]) -> Iterator[Airport]:
    """Emit the airport node for one row of airports.csv."""
    value = identity.value
    yield Airport(
        id=airport_id(value.airport_iata),
        name=value.name,
        city=value.city,
        country=value.country,
    )


AIRPORTS = Mapping(
    name="ops:airport",
    function=make_airport,
    evidence=(
        "Every airport airports.csv describes. The notes' prose about each airport is not read, and the "
        "notes' airport sections do not add airports to this set.",
    ),
)
