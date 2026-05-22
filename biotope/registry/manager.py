"""Registry manager for biotope."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import requests


class RegistryManager:
    """Manages registry operations for biotope."""

    def __init__(self, biotope_root: Path):
        self.biotope_root = biotope_root
        self.cache_dir = biotope_root / ".biotope" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_registry(self, url: str, cache_duration: int = 3600) -> list[dict]:
        """Fetch registry data with caching."""
        cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cache_file = self.cache_dir / f"registry_{cache_key}.json"

        # Check cache first
        if cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age.total_seconds() < cache_duration:
                try:
                    with open(cache_file) as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError) as exc:
                    logging.warning("Corrupted registry cache at %s: %s", cache_file, exc)

        # Fetch from remote
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            registry_data = response.json()

            # Cache the result
            with open(cache_file, "w") as f:
                json.dump(registry_data, f)

            return registry_data
        except (requests.RequestException, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to fetch registry from {url}: {e}")
