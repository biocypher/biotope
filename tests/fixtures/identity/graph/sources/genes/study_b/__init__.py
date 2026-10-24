"""Source registration; the schema and loader beside it are project-owned."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import StudyB


SOURCE = SourceContract(
    name="genes/study_b",
    metadata=Path(__file__).resolve().parent / "../../../../.biotope/datasets/genes.jsonld",
    schema=Path(__file__).with_name("schema.py"),
    records=(StudyB,),
)
