"""Shared terms: meanings that fields of several sources bind to.

A source schema binds its own fields with ``source_field(..., term=TERM)``. Bindings,
value aliases and missing-value tokens stay with each source; matching column names
establish no equivalence. A preserved field needs no term until it is aligned.
"""

from biotope.graph import Term


AIRPORT_IATA = Term(
    "airport_iata",
    "IATA three-letter airport code, as the source writes it. The key on which the airport "
    "table's `iata`, the hub table's `airport_iata` and the notes' airport section are read as "
    "one airport.",
)
AIRLINE_CODE = Term(
    "airline_code",
    "IATA two-character airline code, as the source writes it. The key on which the airline "
    "table's `code` and the hub table's `airline_code` are read as one airline.",
)
AIRLINE_NAME = Term(
    "airline_name",
    "An airline's full marketing name, as the source writes it. The airline table's `name` and "
    "the name the notes give are read as one meaning, joined by exact string equality only: a "
    "normalised, partial or case-insensitive match establishes no identity.",
)


TERMS: tuple[Term, ...] = (AIRPORT_IATA, AIRLINE_CODE, AIRLINE_NAME)
