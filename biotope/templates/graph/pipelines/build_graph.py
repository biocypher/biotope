"""Complete this pipeline for the selected research purpose and source scope."""

from biotope.graph import Pipeline, RunContext

from ..mappings import MAPPINGS
from ..paths import GRAPH_ROOT
from ..sources import SOURCES
from ..topology import TOPOLOGY


def build(context: RunContext) -> None:
    """Load selected inputs, prepare joins, and call registered mappings."""
    # Adapt pipelines/_example.py after registering the actual sources and mappings.
    # Biotope exports emitted objects through BioCypher; no project adapter is needed.
    raise NotImplementedError("Implement the selected pipeline in graph/pipelines/build_graph.py")


PIPELINE = Pipeline(
    name="",  # Set a stable pipeline identity.
    topology=TOPOLOGY,
    sources=SOURCES,
    mappings=MAPPINGS,
    run=build,
    scope="",  # State the selected inputs, output grain and exclusions.
    code_paths=tuple(
        GRAPH_ROOT / path for path in ("__init__.py", "paths.py", "sources", "topology", "mappings", "pipelines")
    ),
    # Existing project intent is discovered when checking from the project root.
    requirements={},
    deferrals={},
    policies={},
    settings={},
)
