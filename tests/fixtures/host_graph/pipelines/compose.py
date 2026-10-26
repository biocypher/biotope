from biotope.graph import RunContext

from ..mappings.person import MAPPING
from ..sources.people.people.loader import load


def run(context: RunContext) -> None:
    for person in load(context):
        context.map(MAPPING, person)
