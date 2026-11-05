"""Source registration; the schema and loader beside it are project-owned."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import HubRow


SOURCE = SourceContract(
    name="data/airports_hubs_csv_hubs",
    metadata=Path(__file__).resolve().parent / "../../../../.biotope/datasets/data.jsonld",
    schema=Path(__file__).with_name("schema.py"),
    records=(HubRow,),
)
