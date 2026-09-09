"""Source contracts selected for the example pipeline."""

from biotope.graph import SourceContract

from .people import SOURCE as PEOPLE
from .samples import SOURCE as SAMPLES


SOURCES: tuple[SourceContract, ...] = (PEOPLE, SAMPLES)
