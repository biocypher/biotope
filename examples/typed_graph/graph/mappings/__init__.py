"""Mappings selected for the example pipeline, one module per group of mappings."""

from biotope.graph import MappingEntry

from .sample import MAPPING, NORMALISE


MAPPINGS: tuple[MappingEntry, ...] = (NORMALISE, MAPPING)
