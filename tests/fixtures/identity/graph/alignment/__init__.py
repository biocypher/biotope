from biotope.graph import Identity, Key, Precedence

from ..sources.genes.study_a import SOURCE as STUDY_A
from ..sources.genes.study_b import SOURCE as STUDY_B
from ..sources.people.directory import SOURCE as DIRECTORY
from ..sources.people.roster import SOURCE as ROSTER
from ..sources.profile.profile_jsonl import SOURCE as PROFILE
from ..sources.publications.openalex import SOURCE as OPENALEX
from ..sources.publications.push import SOURCE as PUSH
from ..topology.gene.node import Gene
from ..topology.paper.node import Paper
from ..topology.person.authored import Authored
from ..topology.person.node import Person


IDENTITIES = (
    Identity(Gene, keys=(Key("ensembl", single=True),), natural="ensembl"),
    Identity(Person, keys=(Key("roster", single=True), Key("orcid", single=True), Key("emails"))),
)

PRECEDENCE = (
    Precedence(Gene, fields={"symbol": (STUDY_A, STUDY_B)}),
    Precedence(
        Person,
        fields={"name": (ROSTER, DIRECTORY, PROFILE), "emails": (ROSTER, DIRECTORY, PROFILE)},
        combine=("emails",),
    ),
    Precedence(Paper, fields={"title": (PUSH, OPENALEX)}),
    Precedence(Authored, fields={"position": (PUSH, OPENALEX)}),
)
