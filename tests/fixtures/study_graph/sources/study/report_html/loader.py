from collections.abc import Iterator
from pathlib import Path

from biotope.graph import Evidence, RunContext, SourceRecord

from . import SOURCE
from .schema import Facts


def _read(path: Path) -> Iterator[SourceRecord[Facts]]:
    path.read_text(encoding="utf-8")
    yield SourceRecord(Facts(), (Evidence(path.as_posix(), "v1", Facts.__record_set__, "body"),))


def load(context: RunContext) -> Iterator[SourceRecord[Facts]]:
    yield from context.load(SOURCE, _read, SOURCE.path())
