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
    name="",  # Set a stable pipeline identity.
    topology=TOPOLOGY,
    sources=SOURCES,
    mappings=MAPPINGS,
    run=run,
    scope="",  # State the selected inputs, output grain and exclusions.
    code_paths=tuple(
        GRAPH_ROOT / path
        for path in (
            "__init__.py",
            "paths.py",
            "standardization.py",
            "alignment",
            "sources",
            "topology",
            "mappings",
            "pipelines",
        )
    ),
    terms=TERMS,
    source_inventory=INVENTORY,
    excluded_sources=EXCLUDED_SOURCES,
    # Existing project intent is discovered when checking from the project root.
    requirements={},
    deferrals={},
    policies={},
    settings={},
)
