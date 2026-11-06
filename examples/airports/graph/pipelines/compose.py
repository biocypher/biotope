"""The build's stage sequence."""

from biotope.graph import RunContext

from ..alignment.airlines import resolve_airlines
from ..alignment.airports import resolve_airports
from ..mappings import AIRLINES, AIRPORTS, ROLES
from ..mappings.role import resolve_roles
from ..sources.airport_role_claims_jsonl.airport_role_claims_jsonl_airport_role_claims.loader import load as load_claims
from ..sources.data.airports_airlines_csv_airlines.loader import load as load_airlines
from ..sources.data.airports_airports_csv_airports.loader import load as load_airports
from ..sources.data.airports_hubs_csv_hubs.loader import load as load_hubs


def run(context: RunContext) -> None:
    """Load each selected source once, resolve identities, then emit the nodes and the role edges."""
    airports = resolve_airports(list(load_airports(context)))
    airlines = resolve_airlines(list(load_airlines(context)))
    hub_rows = list(load_hubs(context))
    claims = list(load_claims(context))

    for code in sorted(airports):
        context.map(AIRPORTS, airports[code])
    for name in sorted(airlines):
        context.map(AIRLINES, airlines[name])

    # Identity is settled above, before anything is admitted, so read order cannot change the result.
    by_code = {record.value.airline_code: record for record in airlines.values()}
    resolution = resolve_roles(claims, hub_rows, airlines, airports)
    for row in resolution.superseded:
        context.exclude("hub_row_superseded_by_notes", row.evidence)
    for role in resolution.roles:
        context.map(ROLES, role, by_code[role.value.airline_code], airports[role.value.airport_iata])

    context.record_audit(
        "airline_roles",
        inputs="every row of airports/hubs.csv and every role claim extracted from data/notes/airport-notes.md",
        outputs="one AirlineRoleAtAirport per airline-airport pair a source states a role for",
        selection=(
            "The notes state the role where they state one; a hub row is admitted where the notes are "
            "silent, since silence is not a denial. A hub row that contradicts the notes is excluded. "
            "Every hub row is accounted for: corroborating, admitted alone, or superseded."
        ),
        counts={
            "notes_claims": len(claims),
            "hub_rows": len(hub_rows),
            "hub_rows_corroborating_notes": resolution.corroborating,
            "hub_rows_admitted_alone": resolution.admitted_alone,
            "hub_rows_superseded": len(resolution.superseded),
            "role_edges": len(resolution.roles),
        },
    )
