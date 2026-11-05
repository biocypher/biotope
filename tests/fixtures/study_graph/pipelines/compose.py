from biotope.graph import RunContext

from ..mappings.person import MAPPING
from ..sources.study.push_people_csv_people.loader import load as load_people
from ..sources.study.report_html.loader import load as load_report


def run(context: RunContext) -> None:
    for person in load_people(context):
        context.map(MAPPING, person)
    for _ in load_report(context):
        pass
