from biotope.graph import Mapping, SourceRecord

from ...sources.publications.openalex.schema import Openalex
from ...sources.publications.push.schema import Push
from ...topology.paper.node import Paper, PaperId
from ...topology.person.authored import Authored
from ...topology.person.node import PersonId


def authorship(doi: str, title: str, orcid: str, position: int | None) -> tuple[Paper, Authored]:
    paper = PaperId(f"doi:{doi}")
    return Paper(paper, title), Authored(PersonId(f"orcid:{orcid}"), paper, position)


def map_push(row: SourceRecord[Push]) -> tuple[Paper, Authored]:
    return authorship(row.value.doi, row.value.title, row.value.orcid, row.value.position)


def map_openalex(row: SourceRecord[Openalex]) -> tuple[Paper, Authored]:
    return authorship(row.value.doi, row.value.title, row.value.orcid, row.value.position)


PUSH_PAPERS = Mapping(name="fixture:push-papers", function=map_push, requirements=("entity:paper", "relation:authored"))
OPENALEX_PAPERS = Mapping(
    name="fixture:openalex-papers", function=map_openalex, requirements=("entity:paper", "relation:authored")
)
