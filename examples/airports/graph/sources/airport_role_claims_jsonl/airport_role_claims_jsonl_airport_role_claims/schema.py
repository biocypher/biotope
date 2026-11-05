# This file is yours to edit; biotope rewrites only its IDs and digest when biotope mv moves its file.
# After any other manifest change, review the drift biotope graph check explains, then update __source_digest__.
"""Typed records for the stored extraction of the notes; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biotope.graph import source_field

from ....standardization import AIRLINE_NAME, AIRPORT_IATA


@dataclass(frozen=True, kw_only=True)
class StoredRoleClaim:
    """One stored claim: one airline the notes name as using one airport in one role."""

    __record_set__: ClassVar[str] = "airport_role_claims.jsonl#airport_role_claims"
    __source_digest__: ClassVar[str] = "a428e09d1f7e4c3b5d739be21fb22a4bfd3d4abb60bbb1168e70911c9f4acf51"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    id: str
    document: str
    airport_iata: str = source_field("airport_iata", term=AIRPORT_IATA)
    airline_name: str = source_field("airline_name", term=AIRLINE_NAME)
    role: str
