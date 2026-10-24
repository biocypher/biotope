"""Source registration; the schema and loader beside it are project-owned."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import Matches


SOURCE = SourceContract(
    name="people/matches",
    metadata=Path(__file__).resolve().parent / "../../../../.biotope/datasets/people.jsonld",
    schema=Path(__file__).with_name("schema.py"),
    records=(Matches,),
)
