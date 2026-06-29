"""Layer 2: DuckDB-backed record streaming and minimal field transforms."""

from biotope.croissant.acquisition.context import AcquisitionContext, RecordRow
from biotope.croissant.acquisition.drift import detect_manifest_drift
from biotope.croissant.acquisition.locations import infer_datasets_location
from biotope.croissant.acquisition.transforms import (
    Transform,
    as_curie,
    compose,
    hash_id,
    passthrough,
    resolve_transform,
)

__all__ = [
    "AcquisitionContext",
    "RecordRow",
    "Transform",
    "as_curie",
    "compose",
    "detect_manifest_drift",
    "hash_id",
    "infer_datasets_location",
    "passthrough",
    "resolve_transform",
]
