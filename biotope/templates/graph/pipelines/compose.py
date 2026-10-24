"""The build's stage sequence."""

from biotope.graph import RunContext


def run(context: RunContext) -> None:
    """Load each selected source once and call the concept mappings; the build merges entities by alignment/."""
    raise NotImplementedError("Author the stage sequence in graph/pipelines/compose.py")
