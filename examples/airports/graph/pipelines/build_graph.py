"""Register the pipeline: its scope, sources, mappings and scientific policies."""

from biotope.graph import Pipeline

from ..mappings import MAPPINGS
from ..paths import GRAPH_ROOT
from ..sources import EXCLUDED_SOURCES, SOURCES
from ..sources.inventory import INVENTORY
from ..standardization import TERMS
from ..topology import TOPOLOGY
from .compose import run


PIPELINE = Pipeline(
    name="ops-airport-roles",
    topology=TOPOLOGY,
    sources=SOURCES,
    mappings=MAPPINGS,
    run=run,
    scope=(
        "Every airport airports/airports.csv describes and every airline airports/airlines.csv lists, "
        "with one AirlineRoleAtAirport edge per airline-airport pair a source states a role for. The role "
        "is the March 2026 notes' where they state one, and hubs.csv's 'hub' where they are silent. The "
        "notes are not a complete inventory, so a pair with no edge is one no source records, not one that "
        "is not a hub or a focus city."
    ),
    code_paths=tuple(
        GRAPH_ROOT / path
        for path in (
            "__init__.py",
            "paths.py",
            "standardization.py",
            "alignment",
            "extraction",
            "sources",
            "topology",
            "mappings",
            "pipelines",
        )
    ),
    terms=TERMS,
    source_inventory=INVENTORY,
    excluded_sources=EXCLUDED_SOURCES,
    policies={
        "hub_row_superseded_by_notes": (
            "hubs.csv states the pair as a hub and the March 2026 notes state a different role for it. "
            "The notes win, so the hub row is not admitted and the pair's edge carries the notes' role."
        ),
    },
    settings={},
)
