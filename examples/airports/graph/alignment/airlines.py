"""Airline identity: the notes' marketing names resolved to the airline table's codes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from biotope.graph import Evidence, SourceRecord

from ..sources.data.airports_airlines_csv_airlines.schema import AirlineRow
from . import where


@dataclass(frozen=True)
class AirlineIdentity:
    """One airline, as the airline table identifies it."""

    airline_code: str
    airline_name: str


def resolve_airlines(rows: Sequence[SourceRecord[AirlineRow]]) -> dict[str, SourceRecord[AirlineIdentity]]:
    """Index every airline by its exact name, the key the notes are resolved on.

    Exact string equality only: the notes' name and the table's `name` are one meaning, but a
    normalised, partial or case-insensitive match establishes no identity. Two rows sharing a
    name contradict each other and fail the build.
    """
    identities: dict[str, AirlineIdentity] = {}
    evidence: dict[str, set[Evidence]] = {}
    for row in rows:
        name = row.value.airline_name
        identity = AirlineIdentity(airline_code=row.value.airline_code, airline_name=name)
        if name in identities and identities[name] != identity:
            raise ValueError(f"{where(row.evidence)}: airports/airlines.csv lists two airlines named {name!r}")
        identities[name] = identity
        evidence.setdefault(name, set()).update(row.evidence)
    return {name: SourceRecord(identities[name], tuple(sorted(evidence[name]))) for name in sorted(identities)}


def require_airline(
    airlines: Mapping[str, SourceRecord[AirlineIdentity]], name: str, evidence: Sequence[Evidence]
) -> SourceRecord[AirlineIdentity]:
    """Return the airline a name denotes, or fail: names are resolved by exact match only."""
    try:
        return airlines[name]
    except KeyError:
        raise ValueError(
            f"{where(evidence)}: the notes name {name!r}, which no airline in airports/airlines.csv has; "
            "names are resolved by exact match, so the build fails rather than inventing an airline"
        ) from None
