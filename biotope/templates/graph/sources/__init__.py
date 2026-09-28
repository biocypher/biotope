"""Select sources from the complete generated inventory; every exclusion states why."""

from biotope.graph import SourceContract

from .inventory import INVENTORY


# Map an inventoried source name, such as "study/samples", to the reason it is left out.
EXCLUDED_SOURCES: dict[str, str] = {}

SOURCES: tuple[SourceContract, ...] = tuple(source for source in INVENTORY if source.name not in EXCLUDED_SOURCES)
