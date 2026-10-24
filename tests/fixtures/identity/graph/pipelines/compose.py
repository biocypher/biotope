from biotope.graph import RunContext

from ..mappings.gene import STUDY_A_GENES, STUDY_B_GENES
from ..mappings.paper import OPENALEX_PAPERS, PUSH_PAPERS
from ..mappings.person import DIRECTORY_PEOPLE, PEOPLE_MATCHES, PROFILE_PEOPLE, ROSTER_PEOPLE
from ..sources.genes.study_a.loader import load as load_study_a
from ..sources.genes.study_b.loader import load as load_study_b
from ..sources.people.directory.loader import load as load_directory
from ..sources.people.matches.loader import load as load_matches
from ..sources.people.roster.loader import load as load_roster
from ..sources.profile.profile_jsonl.loader import load as load_profile
from ..sources.publications.openalex.loader import load as load_openalex
from ..sources.publications.push.loader import load as load_push


def study_a(context: RunContext) -> None:
    for row in load_study_a(context):
        context.map(STUDY_A_GENES, row)


def study_b(context: RunContext) -> None:
    for row in load_study_b(context):
        context.map(STUDY_B_GENES, row)


def roster(context: RunContext) -> None:
    for row in load_roster(context):
        context.map(ROSTER_PEOPLE, row)


def directory(context: RunContext) -> None:
    for row in load_directory(context):
        context.map(DIRECTORY_PEOPLE, row)


def profile(context: RunContext) -> None:
    for record in load_profile(context):
        context.map(PROFILE_PEOPLE, record)


def matches(context: RunContext) -> None:
    for row in load_matches(context):
        context.map(PEOPLE_MATCHES, row)


def push(context: RunContext) -> None:
    for row in load_push(context):
        context.map(PUSH_PAPERS, row)


def openalex(context: RunContext) -> None:
    for row in load_openalex(context):
        context.map(OPENALEX_PAPERS, row)


STAGES = (study_a, study_b, roster, directory, profile, matches, push, openalex)


def run(context: RunContext) -> None:
    for stage in STAGES:
        stage(context)
