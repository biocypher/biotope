"""Author physical decoding here using an established library for the source format."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from biotope.graph import SourceRecord

from .schema import SourceRow


@dataclass(frozen=True)
class Config:
    path: Path
    version: str  # A pinned source release or content digest, not the current time.


def load(config: Config) -> Iterable[SourceRecord[SourceRow]]:
    """Decode values into generated row classes and attach evidence to each result.

    Use biotope.graph.Evidence to return, for each decoded row and locator:
        SourceRecord(row, (Evidence(str(config.path), config.version,
                                    row.__record_set__, locator),))
    A locator identifies the physical record, such as a sheet and row number.
    """
    raise NotImplementedError("Implement a loader for the reviewed source contract")
