"""Select sources from the complete generated inventory; every exclusion states why."""

from biotope.graph import SourceContract

from .inventory import INVENTORY
from .study.people import SOURCE as PEOPLE
from .study.samples import SOURCE as SAMPLES


EXCLUDED_SOURCES: dict[str, str] = {}

SOURCES: tuple[SourceContract, ...] = tuple(source for source in INVENTORY if source.name not in EXCLUDED_SOURCES)

__all__ = ["EXCLUDED_SOURCES", "INVENTORY", "PEOPLE", "SAMPLES", "SOURCES"]
