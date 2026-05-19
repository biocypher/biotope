"""Pluggable registry-client backends."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

import yaml

from biotope.croissant.registry.schema import AdapterMeta


class RegistryClient(Protocol):
    """Common interface every backend implements."""

    def list_adapters(self) -> Iterable[AdapterMeta]:
        """Yield every adapter known to this registry."""
        ...

    def find_by_entity(self, entity_type: str) -> Iterable[AdapterMeta]:
        """Yield adapters that declare ``entity_type`` in ``producedEntities``."""
        ...


class LocalRegistryClient:
    """Read adapter metadata from a local directory of ``meta.yaml`` files.

    Expected layout, mirroring the BioContextAI registry::

        registry_root/
            servers/
                <adapter-id>/
                    meta.yaml
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def list_adapters(self) -> Iterable[AdapterMeta]:
        """Yield every adapter found under ``self.root``."""
        servers_dir = self.root / "servers"
        candidates = servers_dir if servers_dir.is_dir() else self.root
        for path in sorted(candidates.glob("**/meta.yaml")):
            data = yaml.safe_load(path.read_text())
            if data is None:
                continue
            yield AdapterMeta.model_validate(data)

    def find_by_entity(self, entity_type: str) -> Iterable[AdapterMeta]:
        """Yield adapters that declare ``entity_type`` in their produced entities."""
        for meta in self.list_adapters():
            if entity_type in meta.produced_entities:
                yield meta


class HttpRegistryClient:
    """Fetch adapter metadata from a JSON-LD endpoint.

    Looks for ``<base_url>/registry.json`` returning a list of adapter dicts.
    Imports ``httpx`` lazily so users without the ``registry`` extra can still
    use the local backend.
    """

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._cache: list[AdapterMeta] | None = None

    def _fetch(self) -> list[AdapterMeta]:
        if self._cache is not None:
            return self._cache
        try:
            import httpx
        except ImportError:
            msg = (
                "Install the 'registry' extra to use HttpRegistryClient: "
                "uv pip install 'biocypher-croissant[registry]'"
            )
            raise ImportError(msg) from None

        response = httpx.get(f"{self.base_url}/registry.json", timeout=self.timeout)
        response.raise_for_status()
        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") \
            else json.loads(response.text)
        self._cache = [AdapterMeta.model_validate(item) for item in payload]
        return self._cache

    def list_adapters(self) -> Iterable[AdapterMeta]:
        """Yield every adapter from the remote registry."""
        return self._fetch()

    def find_by_entity(self, entity_type: str) -> Iterable[AdapterMeta]:
        """Yield adapters that declare ``entity_type`` in their produced entities."""
        for meta in self._fetch():
            if entity_type in meta.produced_entities:
                yield meta
