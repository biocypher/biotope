"""The role an airline has at an airport, as the desk's notes and hub table state it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from ..airport.node import AirportId
from .node import AirlineId


@dataclass(frozen=True)
class AirlineRoleAtAirport:
    """The role one airline has at one airport, as the desk's sources state it.

    One edge per airline-airport pair. Where the notes state a role, the edge carries the notes' wording (reviewed March 2026); `hubs.csv` is older, and a hub row for the same pair is not admitted as a role of its own. Where the notes are silent, silence is not a denial, so a hub row is admitted with role `hub`. The graph holds only roles a source states: a pair with no edge is one no source records, not one that is not a hub or a focus city.
    """

    schema_id: ClassVar[str] = "ops:airline_role_at_airport"

    source: AirlineId
    target: AirportId
    role: str = field(
        metadata={
            "description": (
                "The role the desk's current source states for this airline at this airport. One of "
                "'hub' or 'focus_city'; no other value occurs. Where the March 2026 notes state a role it "
                "is the notes'; where they are silent it is hubs.csv's 'hub'. The notes' silence is not a "
                "statement that no other role holds, so this is the role recorded, not the only role there is."
            )
        }
    )
