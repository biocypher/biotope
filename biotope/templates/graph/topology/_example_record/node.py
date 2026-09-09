"""Illustrative node; replace its identity and meaning for the research purpose."""

from dataclasses import dataclass
from typing import ClassVar, NewType


RecordId = NewType("RecordId", str)


@dataclass(frozen=True)
class Record:
    schema_id: ClassVar[str] = "example:record"
    id: RecordId
    value: float | None
