"""Airport identity: the IATA code the airport table, the hub table and the notes share."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from biotope.graph import Evidence, SourceRecord

from ..sources.data.airports_airports_csv_airports.schema import AirportRow
from . import where


@dataclass(frozen=True)
class AirportIdentity:
    """One airport, as the airport table identifies it."""

    airport_iata: str
    name: str
    city: str
    country: str


def resolve_airports(rows: Sequence[SourceRecord[AirportRow]]) -> dict[str, SourceRecord[AirportIdentity]]:
    """Index every airport by its IATA code, the key all three sources write it with.

    The code is a key the sources share, so it establishes the match; two rows carrying one
    code with different values contradict each other and fail the build.
    """
    identities: dict[str, AirportIdentity] = {}
    evidence: dict[str, set[Evidence]] = {}
    for row in rows:
        code = row.value.airport_iata
        identity = AirportIdentity(
            airport_iata=code,
            name=row.value.name,
            city=row.value.city,
            country=row.value.country,
        )
        if code in identities and identities[code] != identity:
            raise ValueError(f"{where(row.evidence)}: airports.csv describes {code} twice with different values")
        identities[code] = identity
        evidence.setdefault(code, set()).update(row.evidence)
    return {code: SourceRecord(identities[code], tuple(sorted(evidence[code]))) for code in sorted(identities)}


def require_airport(
    airports: Mapping[str, SourceRecord[AirportIdentity]], iata: str, evidence: Sequence[Evidence]
) -> SourceRecord[AirportIdentity]:
    """Return the airport a claim names, or fail: a code the airport table lacks is a broken reference."""
    try:
        return airports[iata]
    except KeyError:
        raise ValueError(
            f"{where(evidence)}: the claim names airport {iata!r}, which airports/airports.csv does not describe"
        ) from None
