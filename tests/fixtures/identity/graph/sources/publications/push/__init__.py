"""Source registration; the schema and loader beside it are project-owned."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import Push


SOURCE = SourceContract(
    name="publications/push",
    metadata=Path(__file__).resolve().parent / "../../../../.biotope/datasets/publications.jsonld",
    schema=Path(__file__).with_name("schema.py"),
    records=(Push,),
)
