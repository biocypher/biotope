"""Cross-source identity resolution: gather every source's identifiers, then settle them before mappings run."""

from collections.abc import Sequence

from biotope.graph import Evidence


def where(evidence: Sequence[Evidence]) -> str:
    """Name the evidence location a failure is about, so a reader can check it."""
    return str(evidence[0]) if evidence else "the source"
