"""Pydantic schema for adapter ``meta.yaml`` entries.

Mirrors the shape of ``registry/schema.json`` from the BioContextAI registry
and extends it with fields specific to a BioCypher-adapter registry. Only the
extension fields are required for the agent's ``discover_sources`` tool to
function; the schema.org/SoftwareApplication base fields stay optional.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AdapterMeta(BaseModel):
    """Metadata describing one BioCypher adapter in the registry."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    identifier: str
    """``owner/repo`` style identifier, e.g. ``biocypher/open-targets``."""
    name: str
    description: str | None = None
    code_repository: str | None = Field(default=None, alias="codeRepository")
    license: str | None = None
    keywords: list[str] = Field(default_factory=list)

    croissant_file: str | None = Field(default=None, alias="croissantFile")
    """URL or path to the Croissant JSON-LD this adapter consumes."""

    biocypher_schema_config: str | None = Field(default=None, alias="biocypherSchemaConfig")
    """URL or path to the ``schema_config.yaml`` this adapter produces."""

    produced_entities: list[str] = Field(default_factory=list, alias="producedEntities")
    """BioCypher entity types this adapter contributes to a graph."""

    produced_relations: list[str] = Field(default_factory=list, alias="producedRelations")
    """BioCypher relation types this adapter contributes."""
