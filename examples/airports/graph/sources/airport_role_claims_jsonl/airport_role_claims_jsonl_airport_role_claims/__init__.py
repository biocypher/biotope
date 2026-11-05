"""Source registration; the schema and loader beside it are project-owned."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import StoredRoleClaim


SOURCE = SourceContract(
    name="airport_role_claims_jsonl/airport_role_claims_jsonl_airport_role_claims",
    metadata=Path(__file__).resolve().parent / "../../../../.biotope/datasets/data/extracted/airport_role_claims.jsonl.jsonld",
    schema=Path(__file__).with_name("schema.py"),
    records=(StoredRoleClaim,),
)
