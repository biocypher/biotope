"""Declare every extraction: its name, schema, extractor, the files it reads and how many it takes at once."""

from biotope.extraction import Extraction


EXTRACTIONS: tuple[Extraction, ...] = ()
