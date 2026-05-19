"""Layer 3: declarative ``mapping.yaml`` and its compiler."""

from biotope.croissant.mapping.compile import CompiledAdapter, compile_mapping
from biotope.croissant.mapping.defaults import default_mapping
from biotope.croissant.mapping.loader import load_mapping
from biotope.croissant.mapping.model import (
    EdgeMapping,
    EndpointMapping,
    IdMapping,
    Mapping,
    NodeMapping,
)

__all__ = [
    "CompiledAdapter",
    "EdgeMapping",
    "EndpointMapping",
    "IdMapping",
    "Mapping",
    "NodeMapping",
    "compile_mapping",
    "default_mapping",
    "load_mapping",
]
