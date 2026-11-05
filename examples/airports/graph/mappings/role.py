"""The role an airline has at an airport: one edge per airline-airport pair a source states."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from biotope.graph import Evidence, Mapping, SourceRecord

from ..alignment import where
from ..alignment.airlines import AirlineIdentity, require_airline
from ..alignment.airports import AirportIdentity, require_airport
from ..sources.airport_role_claims_jsonl.airport_role_claims_jsonl_airport_role_claims.schema import StoredRoleClaim
from ..sources.data.airports_hubs_csv_hubs.schema import HubRow
from ..topology.airline.airline_role_at_airport import AirlineRoleAtAirport
from ..topology.airline.node import airline_id
from ..topology.airport.node import airport_id


@dataclass(frozen=True)
class ResolvedRole:
    """One airline-airport pair's role, settled from the notes and the hub table."""

    airport_iata: str
    airline_code: str
    role: str


@dataclass(frozen=True)
class RoleResolution:
    """One run's settled roles, and how every hub row was accounted for.

    Every hub row is one of three: it corroborates a notes claim (its evidence joins that
    edge), it is admitted alone because the notes are silent, or it is superseded by the notes
    and excluded. Nothing is dropped without a count.
    """

    roles: list[SourceRecord[ResolvedRole]]
    superseded: list[SourceRecord[HubRow]]
    corroborating: int
    admitted_alone: int


def _role(raw: str, evidence: Sequence[Evidence]) -> str:
    if raw in ("hub", "focus_city"):
        return raw
    raise ValueError(f"{where(evidence)}: the stored claim states the role {raw!r}, not 'hub' or 'focus_city'")


def resolve_roles(
    claims: Sequence[SourceRecord[StoredRoleClaim]],
    hub_rows: Sequence[SourceRecord[HubRow]],
    airlines: dict[str, SourceRecord[AirlineIdentity]],
    airports: dict[str, SourceRecord[AirportIdentity]],
) -> RoleResolution:
    """Settle one role per airline-airport pair, and account for every hub row.

    The notes state the role wherever they state one, and every claim is resolved to an airline
    code and an airport before it is admitted. A hub row whose pair the notes do not mention is
    admitted as a hub, because the notes' silence is not a denial. A hub row whose pair the notes
    do mention with another role is returned separately, for the caller to exclude.
    """
    hub_by_pair: dict[tuple[str, str], SourceRecord[HubRow]] = {}
    for row in hub_rows:
        pair = (row.value.airport_iata, row.value.airline_code)
        if pair in hub_by_pair:
            raise ValueError(f"{where(row.evidence)}: airports/hubs.csv states the pair {pair} more than once")
        hub_by_pair[pair] = row

    roles: list[SourceRecord[ResolvedRole]] = []
    superseded: list[SourceRecord[HubRow]] = []
    claimed: set[tuple[str, str]] = set()
    corroborating = 0

    for claim in claims:
        iata = claim.value.airport_iata
        name = claim.value.airline_name
        role = _role(claim.value.role, claim.evidence)
        airline = require_airline(airlines, name, claim.evidence)
        require_airport(airports, iata, claim.evidence)
        pair = (iata, airline.value.airline_code)
        if pair in claimed:
            raise ValueError(f"{where(claim.evidence)}: the notes state more than one role for {pair}")
        claimed.add(pair)

        hub = hub_by_pair.get(pair)
        evidence = claim.evidence
        if hub is not None:
            if role == "hub":
                corroborating += 1
                evidence = claim.evidence + hub.evidence
            else:
                superseded.append(hub)
        roles.append(
            SourceRecord(
                ResolvedRole(
                    airport_iata=iata,
                    airline_code=airline.value.airline_code,
                    role=role,
                ),
                evidence,
            )
        )

    alone = sorted(set(hub_by_pair) - claimed)
    known_codes = {record.value.airline_code for record in airlines.values()}
    for pair in alone:
        row = hub_by_pair[pair]
        iata, code = pair
        require_airport(airports, iata, row.evidence)
        if code not in known_codes:
            raise ValueError(
                f"{where(row.evidence)}: airports/hubs.csv names airline code {code!r}, "
                "which airports/airlines.csv does not list"
            )
        roles.append(
            SourceRecord(
                ResolvedRole(airport_iata=iata, airline_code=code, role="hub"),
                row.evidence,
            )
        )

    return RoleResolution(
        roles=roles,
        superseded=superseded,
        corroborating=corroborating,
        admitted_alone=len(alone),
    )


def make_role_edge(
    role: SourceRecord[ResolvedRole],
    airline: SourceRecord[AirlineIdentity],
    airport: SourceRecord[AirportIdentity],
) -> Iterator[AirlineRoleAtAirport]:
    """Emit the edge for one settled airline-airport pair."""
    yield AirlineRoleAtAirport(
        source=airline_id(airline.value.airline_code),
        target=airport_id(airport.value.airport_iata),
        role=role.value.role,
    )


ROLES = Mapping(
    name="ops:airline-role-at-airport",
    function=make_role_edge,
    evidence=(
        "One edge per airline-airport pair a source states a role for. The notes' role wins where they "
        "state one; hubs.csv's hub is admitted where the notes are silent. The graph asserts no role for "
        "a pair no source states one for.",
    ),
)
