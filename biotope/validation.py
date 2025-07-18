"""Validation utilities for biotope metadata."""

import json
import yaml
import requests
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


def load_biotope_config(biotope_root: Path) -> Dict:
    """Load biotope configuration from .biotope/config/biotope.yaml."""
    config_path = biotope_root / ".biotope" / "config" / "biotope.yaml"
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
        "field_validation": validation_config.get("field_validation", {})
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
        with open(cache_file, 'w') as f:
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
    path = parsed_url.path.lstrip('/')
    if path.endswith('.yaml') or path.endswith('.yml'):
        # Remove the extension since we'll add .yaml
        path = path[:-5] if path.endswith('.yaml') else path[:-4]
    
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


def is_metadata_annotated(metadata: Dict, config: Dict) -> Tuple[bool, List[str]]:
    """
    Check if metadata meets the minimum annotation requirements.
    
    Args:
        metadata: The metadata dictionary to validate
        config: Biotope configuration dictionary
        
    Returns:
        Tuple of (is_annotated, list_of_validation_errors)
    """
    validation_config = config.get("annotation_validation", {})
    
    # If validation is disabled, consider everything annotated
    if not validation_config.get("enabled", True):
        return True, []
    
    # Use default validation if no validation config is present
    if not validation_config:
        # Default validation requirements
        required_fields = ["name", "description", "creator", "dateCreated", "distribution"]
        field_validation = {
            "name": {"type": "string", "min_length": 1},
            "description": {"type": "string", "min_length": 10},
            "creator": {"type": "object", "required_keys": ["name"]},
            "dateCreated": {"type": "string", "format": "date"},
            "distribution": {"type": "array", "min_length": 1}
        }
    else:
        required_fields = validation_config.get("minimum_required_fields", [])
        field_validation = validation_config.get("field_validation", {})
    
    errors = []
    
    # Check for required fields
    for field in required_fields:
        if field not in metadata:
            errors.append(f"Missing required field: {field}")
            continue
        
        # Validate field according to field_validation rules
        field_errors = _validate_field(metadata[field], field, field_validation.get(field, {}))
        errors.extend(field_errors)
    
    return len(errors) == 0, errors


def _validate_field(value: any, field_name: str, validation_rules: Dict) -> List[str]:
    """Validate a single field according to validation rules."""
    errors = []
    
    # Type validation
    expected_type = validation_rules.get("type")
    if expected_type:
        if expected_type == "string" and not isinstance(value, str):
            errors.append(f"Field '{field_name}' must be a string")
        elif expected_type == "object" and not isinstance(value, dict):
            errors.append(f"Field '{field_name}' must be an object")
        elif expected_type == "array" and not isinstance(value, list):
            errors.append(f"Field '{field_name}' must be an array")
    
    # String-specific validations
    if isinstance(value, str) and expected_type == "string":
        min_length = validation_rules.get("min_length")
        if min_length and len(value.strip()) < min_length:
            errors.append(f"Field '{field_name}' must be at least {min_length} characters")
    
    # Object-specific validations
    if isinstance(value, dict) and expected_type == "object":
        required_keys = validation_rules.get("required_keys", [])
        for key in required_keys:
            if key not in value:
                errors.append(f"Field '{field_name}' must contain key: {key}")
    
    # Array-specific validations
    if isinstance(value, list) and expected_type == "array":
        min_length = validation_rules.get("min_length")
        if min_length and len(value) < min_length:
            errors.append(f"Field '{field_name}' must contain at least {min_length} items")
    
    # Date format validation
    if field_name == "dateCreated" and isinstance(value, str):
        try:
            datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            errors.append(f"Field '{field_name}' must be a valid ISO date format")
    
    return errors


def get_annotation_status_for_files(biotope_root: Path, file_paths: List[str]) -> Dict[str, Tuple[bool, List[str]]]:
    """
    Get annotation status for multiple metadata files.
    
    Args:
        biotope_root: Path to biotope project root
        file_paths: List of file paths relative to biotope_root
        
    Returns:
        Dictionary mapping file paths to (is_annotated, validation_errors)
    """
    config = load_biotope_config(biotope_root)
    results = {}
    
    for file_path in file_paths:
        if not file_path.endswith('.jsonld'):
            continue
            
        metadata_file = biotope_root / file_path
        if not metadata_file.exists():
            results[file_path] = (False, ["Metadata file not found"])
            continue
        
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)
            
            is_annotated, errors = is_metadata_annotated(metadata, config)
            results[file_path] = (is_annotated, errors)
            
        except (json.JSONDecodeError, IOError) as e:
            results[file_path] = (False, [f"Error reading metadata: {str(e)}"])
    
    return results


def get_all_tracked_files(biotope_root: Path) -> List[str]:
    """Get all tracked metadata files in the biotope project."""
    datasets_dir = biotope_root / ".biotope" / "datasets"
    if not datasets_dir.exists():
        return []
    
    tracked_files = []
    for metadata_file in datasets_dir.rglob("*.jsonld"):
        # Get the relative path from biotope_root
        relative_path = metadata_file.relative_to(biotope_root)
        tracked_files.append(str(relative_path))
    
    return tracked_files


def get_staged_metadata_files(biotope_root: Path) -> List[str]:
    """Get all staged metadata files using Git."""
    import subprocess
    
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=biotope_root,
            capture_output=True,
            text=True,
            check=True
        )
        
        staged_files = []
        for file_path in result.stdout.splitlines():
            if file_path.startswith(".biotope/datasets/") and file_path.endswith(".jsonld"):
                staged_files.append(file_path)
        
        return staged_files
        
    except subprocess.CalledProcessError:
        return [] 