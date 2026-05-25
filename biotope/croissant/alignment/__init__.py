"""Layer 4: cross-Croissant alignment.

Combine the outputs of several :class:`CompiledAdapter` instances into one
BioCypher graph. The alignment file declares equivalences between IDs across
Croissant files; at build time those IDs are rewritten to a canonical form so
duplicate entities collapse.
"""

from biotope.croissant.alignment.loader import load_alignment
from biotope.croissant.alignment.merge import MergedAdapter, merge_adapters
from biotope.croissant.alignment.model import (
    Alignment,
    Equivalence,
    EquivalenceKind,
    Reference,
)

__all__ = [
    "Alignment",
    "Equivalence",
    "EquivalenceKind",
    "MergedAdapter",
    "Reference",
    "load_alignment",
    "merge_adapters",
]
