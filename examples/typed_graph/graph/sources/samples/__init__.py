"""Reviewed samples contract; its record inventory is generated."""

from biotope.graph import SourceContract

from ...paths import GRAPH_ROOT, PROJECT_ROOT
from .schema import RECORDS


SOURCE = SourceContract(
    name="samples",
    metadata=PROJECT_ROOT / ".biotope/datasets/samples.jsonld",
    generated=GRAPH_ROOT / "sources/samples/schema.py",
    records=RECORDS,
)
