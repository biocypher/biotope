"""Croissant metadata models, mapping definitions and structural validation.

Source-format parsing belongs to croissant-baker. Downstream graph modules are
currently unsupported and are not imported by the metadata workflow.
"""

from biotope.croissant.spec import (
    CroissantDatasetModel,
    CroissantFieldModel,
    CroissantRecordSetModel,
    load_from_path,
    load_from_url,
)

__all__ = [
    "CroissantDatasetModel",
    "CroissantFieldModel",
    "CroissantRecordSetModel",
    "load_from_path",
    "load_from_url",
]
