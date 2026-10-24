"""Source registration; the schema and loader beside it are project-owned."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import Roster


SOURCE = SourceContract(
    name="people/roster",
    metadata=Path(__file__).resolve().parent / "../../../../.biotope/datasets/people.jsonld",
    schema=Path(__file__).with_name("schema.py"),
    records=(Roster,),
)
