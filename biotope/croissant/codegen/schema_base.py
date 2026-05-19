"""Runtime base classes used by the generated schema module.

Ported from open-targets/open_targets/data/schema_base.py and made
dataset-agnostic.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Sequence
from typing import Final

from biotope.croissant.spec import FieldKind


class Dataset:
    """Base class for a generated dataset (one per Croissant record set)."""

    id: Final[str]
    fields: Final[Sequence[type[Field]]]


class Field(ABC):
    """Base class for a generated field."""

    name: Final[str]
    kind: Final[FieldKind]
    dataset: Final[type[Dataset]]
    path: Final[Sequence[type[Dataset] | type[Field]]]


class ScalarField(Field):
    """Field with a scalar (non-nested, non-repeated) value."""


class StructField(Field):
    """Field with sub-fields."""

    fields: Final[Sequence[type[Field]]]


class SequenceField(Field):
    """Repeated field; ``element`` describes the element type."""

    element: Final[type[Field]]
