"""Croissant-driven knowledge-graph construction for biotope.

Layers, lowest first:

* :mod:`biotope.croissant.spec` — typed Pydantic models for Croissant 1.1 JSON-LD
* :mod:`biotope.croissant.codegen` — Jinja schema codegen from a Croissant model
* :mod:`biotope.croissant.acquisition` — DuckDB-backed record streaming + transforms
* :mod:`biotope.croissant.mapping` — declarative ``mapping.yaml`` and its compiler
* :mod:`biotope.croissant.alignment` — cross-Croissant alignment (``alignment.yaml``)
* :mod:`biotope.croissant.scaffold` — write a runnable BioCypher project from mappings
* :mod:`biotope.croissant.registry` — pluggable BioCypher-adapter registry clients

The agent surface is the biotope CLI; there is no separate MCP server.
"""

from biotope.croissant.spec import (
    CroissantDatasetModel,
    CroissantFieldModel,
    CroissantRecordSetModel,
    load_from_path,
    load_from_url,
)

__all__ = [
    "CroissantDatasetModel",
    "CroissantFieldModel",
    "CroissantRecordSetModel",
    "load_from_path",
    "load_from_url",
]
