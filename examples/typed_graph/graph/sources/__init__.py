"""Source contracts selected for the example pipeline.

Generation writes one package per record set of graph/metadata/study.jsonld and
a study.CONTRACTS inventory over them; selecting from it stays a project choice.
"""

from biotope.graph import SourceContract

from .study.people import SOURCE as PEOPLE
from .study.samples import SOURCE as SAMPLES


SOURCES: tuple[SourceContract, ...] = (PEOPLE, SAMPLES)
