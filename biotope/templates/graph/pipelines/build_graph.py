"""Complete this pipeline for the selected research purpose and source scope."""

from biotope.graph import Pipeline, RunContext

from ..checks import VALIDATION_CHECKS
from ..mappings import MAPPINGS
from ..paths import GRAPH_ROOT
from ..query_context import QUERY_CONTEXT
from ..sources import SOURCES
from ..topology import TOPOLOGY


def build(context: RunContext) -> None:
    """Load selected inputs, prepare joins, and call registered mappings."""
    # Adapt pipelines/_example.py after registering the actual sources and mappings.
    # Biotope exports emitted objects through BioCypher; no project adapter is needed.
    # Record one audit per stage that selects, joins or aggregates, so that a row
    # the pipeline silently never emitted is visible as a count rather than absence.
    raise NotImplementedError("Implement the selected pipeline in graph/pipelines/build_graph.py")


PIPELINE = Pipeline(
    name="",  # Set a stable pipeline identity.
    topology=TOPOLOGY,
    sources=SOURCES,
    mappings=MAPPINGS,
    run=build,
    scope="",  # State the selected inputs, output grain and exclusions.
    code_paths=tuple(
        GRAPH_ROOT / path
        for path in (
            "__init__.py",
            "paths.py",
            "checks.py",
            "query_context.py",
            "sources",
            "topology",
            "mappings",
            "pipelines",
        )
    ),
    # Existing project intent is discovered when checking from the project root.
    requirements={},
    deferrals={},
    policies={},
    settings={},
    # What the graph claims to answer, what a reader must know to query it, and
    # the executable checks that decide whether those claims hold.
    query_context=QUERY_CONTEXT,
    validation_checks=VALIDATION_CHECKS,
)
