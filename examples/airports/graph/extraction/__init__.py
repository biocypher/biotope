"""Declare every extraction: its name, schema, extractor, the files it reads and how many it takes at once."""

from biotope.extraction import Extraction

from .airport_notes import AirportNotesReader, AirportRoleClaim


EXTRACTIONS: tuple[Extraction, ...] = (
    Extraction(
        name="airport_role_claims",
        schema=AirportRoleClaim,
        extractor=AirportNotesReader,
        files=("data/notes/*.md",),
        parallel=1,
    ),
)
