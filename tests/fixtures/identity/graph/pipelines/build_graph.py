from biotope.graph import Pipeline

from ..alignment import IDENTITIES, PRECEDENCE
from ..mappings import MAPPINGS
from ..paths import GRAPH_ROOT, PROJECT_ROOT
from ..sources import EXCLUDED_SOURCES, SOURCES
from ..sources.inventory import INVENTORY
from ..standardization import TERMS
from ..topology import TOPOLOGY
from .compose import run


PIPELINE = Pipeline(
    name="fixture:identity",
    topology=TOPOLOGY,
    sources=SOURCES,
    mappings=MAPPINGS,
    run=run,
    scope=(
        "Every row of two invented gene studies, an invented roster and directory, "
        "extracted profile pages and two publication lists."
    ),
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
    intent=PROJECT_ROOT / "project.yaml",
    requirements={
        "entity:gene": "fixture:gene",
        "entity:person": "fixture:person",
        "entity:paper": "fixture:paper",
        "relation:authored": "fixture:authored",
    },
    identities=IDENTITIES,
    precedence=PRECEDENCE,
)
