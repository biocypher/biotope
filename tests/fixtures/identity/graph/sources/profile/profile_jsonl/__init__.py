"""Source registration; the schema and loader beside it are project-owned."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import ProfileJsonl


SOURCE = SourceContract(
    name="profile/profile_jsonl",
    metadata=Path(__file__).resolve().parent / "../../../../.biotope/datasets/extracted/profile.jsonld",
    schema=Path(__file__).with_name("schema.py"),
    records=(ProfileJsonl,),
)
