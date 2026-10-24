from dataclasses import dataclass, field
from typing import ClassVar, NewType


GeneId = NewType("GeneId", str)


@dataclass(frozen=True)
class Gene:
    """A gene that at least one study reports, one entity per Ensembl gene ID across studies."""

    schema_id: ClassVar[str] = "fixture:gene"
    id: GeneId
    ensembl: str | None = field(metadata={"description": "The Ensembl gene ID, without a version."})
    symbol: str = field(metadata={"description": "The gene symbol as the study gives it."})
