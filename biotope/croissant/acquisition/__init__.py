"""Metadata path and file-tracking helpers; no source record loading."""

from biotope.croissant.acquisition.drift import detect_manifest_drift
from biotope.croissant.acquisition.locations import infer_datasets_location

__all__ = ["detect_manifest_drift", "infer_datasets_location"]
