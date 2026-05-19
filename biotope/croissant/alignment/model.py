"""Pydantic model for ``alignment.yaml``.

Example::

    mappings:
      - ot.mapping.yaml
      - collectri.mapping.yaml
    equivalences:
      - a: ot.gene
        b: collectri.tf
        kind: same_node
        join_on:
          a: ensembl_id
          b: ensembl_id

The ``kind`` field is open-ended; ``same_node`` is the only kind v1 implements,
but ``similarity``/``embedding`` are reserved so a future entity-resolution
backend can plug in without breaking the schema.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EquivalenceKind(str, Enum):
    """How two references should be reconciled."""

    SAME_NODE = "same_node"
    """A row in mapping A and a row in mapping B refer to the same entity when
    their join fields are equal. The two IDs are unified to a canonical CURIE.
    """

    SIMILARITY = "similarity"
    """Reserved for a future embedding-based entity-resolution backend."""


class Reference(_Model):
    """Pointer to a node type within one of the mappings under alignment.

    The ``mapping`` field is the *stem* of the mapping file (basename without
    suffix) so cross-references stay stable when mappings are renamed.
    """

    mapping: str
    """Stem of the mapping file (e.g. ``ot`` for ``ot.mapping.yaml``)."""
    node_type: str


class JoinKeys(_Model):
    """Field-level join keys for a :class:`Equivalence`."""

    a: str
    b: str


class Equivalence(_Model):
    """One alignment row."""

    a: Reference
    b: Reference
    kind: EquivalenceKind = EquivalenceKind.SAME_NODE
    join_on: JoinKeys


class Alignment(_Model):
    """Top-level ``alignment.yaml``."""

    mappings: list[str] = Field(default_factory=list)
    """Paths to the ``mapping.yaml`` files participating in the alignment."""
    equivalences: list[Equivalence] = Field(default_factory=list)
