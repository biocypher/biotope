"""Validation utilities for biotope metadata."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
import yaml


def load_biotope_config(biotope_root: Path) -> Dict:
    """Load biotope configuration from .biotope/config.yaml."""
    config_path = biotope_root / ".biotope" / "config.yaml"
    if not config_path.exists():
        return {}

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except (yaml.YAMLError, IOError):
        return {}

    # Check for remote validation configuration
    validation_config = config.get("annotation_validation", {})
    remote_config = validation_config.get("remote_config", {})

    if remote_config and remote_config.get("url"):
        remote_validation = _load_remote_validation_config(remote_config, biotope_root)
        if remote_validation:
            # Merge remote config with local config (local takes precedence)
            merged_validation = _merge_validation_configs(remote_validation, validation_config)
            config["annotation_validation"] = merged_validation

    return config


def get_validation_pattern(biotope_root: Path) -> str:
    """
    Get the validation pattern used by this project.

    This allows cluster administrators to check which projects are using
    the correct validation pattern for their requirements.

    Args:
        biotope_root: Path to the biotope project root.

    Returns:
        String identifying the validation pattern (e.g., "default", "cluster-strict", "storage-management")
    """
    config = load_biotope_config(biotope_root)
    validation_config = config.get("annotation_validation", {})

    # Check for explicit validation pattern
    pattern = validation_config.get("validation_pattern", "default")

    # If using remote validation, include that in the pattern name
    remote_config = validation_config.get("remote_config", {})
    if remote_config and remote_config.get("url"):
        url = remote_config.get("url", "")
        if "cluster" in url.lower() or "hpc" in url.lower():
            pattern = f"cluster-{pattern}"
        elif "storage" in url.lower() or "archive" in url.lower():
            pattern = f"storage-{pattern}"

    return pattern


def get_validation_info(biotope_root: Path) -> Dict:
    """
    Get comprehensive validation information for this project.

    This provides cluster administrators with all the information they need
    to verify that projects are using appropriate validation patterns.

    Args:
        biotope_root: Path to the biotope project root.

    Returns:
        Dictionary with validation pattern, requirements, and configuration details
    """
    config = load_biotope_config(biotope_root)
    validation_config = config.get("annotation_validation", {})

    info = {
        "validation_pattern": get_validation_pattern(biotope_root),
        "enabled": validation_config.get("enabled", True),
        "required_fields": validation_config.get("minimum_required_fields", []),
        "remote_configured": False,
        "remote_url": None,
        "field_validation": validation_config.get("field_validation", {}),
    }

    # Add remote validation info if configured
    remote_config = validation_config.get("remote_config", {})
    if remote_config and remote_config.get("url"):
        info["remote_configured"] = True
        info["remote_url"] = remote_config.get("url")
        info["cache_duration"] = remote_config.get("cache_duration", 3600)
        info["fallback_to_local"] = remote_config.get("fallback_to_local", True)

    return info


def _load_remote_validation_config(remote_config: Dict, biotope_root: Path) -> Optional[Dict]:
    """Load validation configuration from a remote URL with caching."""
    url = remote_config["url"]
    cache_duration = remote_config.get("cache_duration", 3600)  # 1 hour default
    fallback_to_local = remote_config.get("fallback_to_local", True)

    # Check cache first
    cache_file = _get_cache_file_path(url, biotope_root)
    if cache_file.exists():
        cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if cache_age.total_seconds() < cache_duration:
            try:
                with open(cache_file) as f:
                    return yaml.safe_load(f)
            except (yaml.YAMLError, IOError):
                pass

    # Fetch from remote
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        remote_config_data = yaml.safe_load(response.text)

        # Cache the result
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w") as f:
            yaml.dump(remote_config_data, f)

        return remote_config_data

    except (requests.RequestException, yaml.YAMLError) as e:
        if fallback_to_local:
            return None  # Will fall back to local config
        else:
            raise ValueError(f"Failed to load remote validation config from {url}: {e}")


def _get_cache_file_path(url: str, biotope_root: Path) -> Path:
    """Get the cache file path for a remote URL."""
    # Create a filename from the URL
    parsed_url = urlparse(url)

    # Clean up the path: remove leading slash and handle file extensions
    path = parsed_url.path.lstrip("/")
    if path.endswith(".yaml") or path.endswith(".yml"):
        # Remove the extension since we'll add .yaml
        path = path[:-5] if path.endswith(".yaml") else path[:-4]

    # Create filename: netloc_path.yaml
    filename = f"{parsed_url.netloc.replace('.', '_')}_{path.replace('/', '_')}.yaml"
    return biotope_root / ".biotope" / "cache" / "validation" / filename


def _merge_validation_configs(remote_config: Dict, local_config: Dict) -> Dict:
    """Merge remote and local validation configurations (local takes precedence)."""
    merged = remote_config.copy()

    # Merge required fields (local can add to remote)
    remote_fields = set(remote_config.get("minimum_required_fields", []))
    local_fields = set(local_config.get("minimum_required_fields", []))
    merged["minimum_required_fields"] = list(remote_fields | local_fields)

    # Merge field validation (local overrides remote)
    remote_field_validation = remote_config.get("field_validation", {})
    local_field_validation = local_config.get("field_validation", {})
    merged["field_validation"] = {**remote_field_validation, **local_field_validation}

    # Preserve other local settings
    for key, value in local_config.items():
        if key not in ["minimum_required_fields", "field_validation"]:
            merged[key] = value

    return merged
