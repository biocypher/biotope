"""Reviewed people contract; its record inventory is generated."""

from biotope.graph import SourceContract

from ...paths import GRAPH_ROOT, PROJECT_ROOT
from .schema import RECORDS


SOURCE = SourceContract(
    name="people",
    metadata=PROJECT_ROOT / ".biotope/datasets/people.jsonld",
    generated=GRAPH_ROOT / "sources/people/schema.py",
    records=RECORDS,
)
