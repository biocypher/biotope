from biotope.graph import SourceContract

from .inventory import INVENTORY
from .study.push_people_csv_people import SOURCE as PEOPLE
from .study.report_html import SOURCE as REPORT


SOURCES: tuple[SourceContract, ...] = (PEOPLE, REPORT)
EXCLUDED_SOURCES: dict[str, str] = {
    source.name: "A new input; select it once its loader is written" for source in INVENTORY if source not in SOURCES
}
