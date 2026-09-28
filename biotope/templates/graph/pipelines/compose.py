"""The build's stage sequence."""

from biotope.graph import RunContext


def run(context: RunContext) -> None:
    """Load each selected source once, resolve identities in alignment/, then call the concept mappings."""
    raise NotImplementedError("Author the stage sequence in graph/pipelines/compose.py")
