"""Pydantic model for ``mapping.yaml``.

Schema sketch::

    croissant: ./targets.croissant.json
    nodes:
      - record_set: targets
        type: gene
        id:
          from: ensembl_id
          transform: as_curie
          args: {prefix: ensembl}
        properties: [symbol, biotype]
    edges:
      - record_set: target_disease_assoc
        type: gene_associated_with_disease
        source: {from: target_id, transform: as_curie, args: {prefix: ensembl}}
        target: {from: disease_id, transform: as_curie, args: {prefix: mondo}}
        properties: [score]

``transform`` defaults to ``passthrough`` so the simplest mapping doesn't need
to mention it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EndpointMapping(_Model):
    """How to derive a node ID from a row (also used for edge source/target)."""

    from_: str = Field(alias="from")
    transform: str = "passthrough"
    args: dict[str, Any] = Field(default_factory=dict)
    """Extra keyword arguments for ``transform``. ``args.field`` is omitted; the
    compiler injects ``from`` as the ``field`` kwarg automatically."""


IdMapping = EndpointMapping


class NodeMapping(_Model):
    """One node type emitted from one record set."""

    record_set: str
    type: str
    id: IdMapping
    properties: list[str] = Field(default_factory=list)
    where: str | None = None
    """Optional SQL ``WHERE`` clause applied at acquisition time."""


class EdgeMapping(_Model):
    """One edge type emitted from one record set."""

    record_set: str
    type: str
    source: EndpointMapping
    target: EndpointMapping
    properties: list[str] = Field(default_factory=list)
    where: str | None = None


class Mapping(_Model):
    """Top-level ``mapping.yaml``."""

    croissant: str
    """Path or URL to the Croissant JSON-LD file this mapping applies to."""
    nodes: list[NodeMapping] = Field(default_factory=list)
    edges: list[EdgeMapping] = Field(default_factory=list)
