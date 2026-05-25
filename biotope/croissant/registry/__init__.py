"""Layer 6: client for the BioCypher-adapter registry.

The registry itself is a separate, bespoke deliverable (not BioContextAI,
which only indexes MCP servers). This client speaks to a JSON-LD endpoint
that follows the same shape conventions as the BioContextAI registry,
extended with the optional ``croissantFile``, ``biocypherSchemaConfig``,
``producedEntities`` and ``producedRelations`` fields.

Two swappable backends are provided so this package can be tested and used
before the production registry exists:

* :class:`LocalRegistryClient` — reads ``meta.yaml`` files from a local directory.
* :class:`HttpRegistryClient` — fetches ``/registry.json`` from a base URL.
"""

from biotope.croissant.registry.client import (
    HttpRegistryClient,
    LocalRegistryClient,
    RegistryClient,
)
from biotope.croissant.registry.schema import AdapterMeta

__all__ = [
    "AdapterMeta",
    "HttpRegistryClient",
    "LocalRegistryClient",
    "RegistryClient",
]
