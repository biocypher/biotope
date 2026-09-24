"""Mappings selected for the example pipeline, organized by concept: mappings/<concept>/."""

from biotope.graph import MappingEntry

from .sample import MAPPING, NORMALISE


MAPPINGS: tuple[MappingEntry, ...] = (NORMALISE, MAPPING)
