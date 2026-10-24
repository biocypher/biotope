from collections.abc import Iterator

from biotope.graph import Mapping, SourceRecord

from ...sources.genes.study_a.schema import StudyA
from ...sources.genes.study_b.schema import StudyB
from ...topology.gene.node import Gene, GeneId


def map_study_a(row: SourceRecord[StudyA]) -> Iterator[Gene]:
    yield Gene(GeneId(f"study_a:{row.value.row}"), row.value.ensembl, row.value.symbol)


def map_study_b(row: SourceRecord[StudyB]) -> Iterator[Gene]:
    yield Gene(GeneId(f"study_b:{row.value.row}"), row.value.ensembl, row.value.symbol)


STUDY_A_GENES = Mapping(name="fixture:study-a-genes", function=map_study_a, requirements=("entity:gene",))
STUDY_B_GENES = Mapping(name="fixture:study-b-genes", function=map_study_b, requirements=("entity:gene",))
