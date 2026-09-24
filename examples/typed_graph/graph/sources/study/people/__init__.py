"""Source registration; the schema and loader beside it are project-owned."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import People


SOURCE = SourceContract(
    name="study/people",
    metadata=Path(__file__).resolve().parent / "../../../../.biotope/datasets/study.jsonld",
    schema=Path(__file__).with_name("schema.py"),
    records=(People,),
)
