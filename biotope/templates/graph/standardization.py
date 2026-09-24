"""Shared terms: meanings that fields of several sources bind to.

A source schema binds its own fields with ``source_field(..., term=TERM)``. Bindings,
value aliases and missing-value tokens stay with each source; matching column names
establish no equivalence. A preserved field needs no term until it is aligned.
"""

from biotope.graph import Term


TERMS: tuple[Term, ...] = ()
