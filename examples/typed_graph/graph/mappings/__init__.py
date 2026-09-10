"""Mappings selected for the example pipeline."""

from biotope.graph import MappingEntry

from .samples import MAPPING, NORMALISE


MAPPINGS: tuple[MappingEntry, ...] = (NORMALISE, MAPPING)
