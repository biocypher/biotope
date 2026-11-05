"""Source registration; the schema and loader beside it are project-owned."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import AirportRow


SOURCE = SourceContract(
    name="data/airports_airports_csv_airports",
    metadata=Path(__file__).resolve().parent / "../../../../.biotope/datasets/data.jsonld",
    schema=Path(__file__).with_name("schema.py"),
    records=(AirportRow,),
)
