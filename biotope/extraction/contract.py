from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, cast

from biotope.extraction.schema import Schema


@dataclass(frozen=True)
class Document:
    path: Path
    sha256: str


class ExtractionError(Exception):
    pass


class Extractor(ABC):
    name: ClassVar[str]
    version: ClassVar[str]
    settings: ClassVar[Mapping[str, object]] = {}

    @abstractmethod
    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class Extraction:
    name: str
    schema: type
    extractor: type[Extractor]
    files: tuple[str, ...]
    parallel: int = 1

    def __post_init__(self) -> None:
        name, extractor, files, parallel = cast(
            tuple[object, ...], (self.name, self.extractor, self.files, self.parallel)
        )
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError(f"Extraction name {name!r}: use lowercase letters, digits and underscores")
        Schema.from_class(self.schema)
        if not isinstance(extractor, type) or not issubclass(extractor, Extractor):
            raise ValueError(f"{name}: the extractor must be a subclass of biotope.extraction.Extractor")
        for attribute in ("name", "version"):
            value: object = getattr(extractor, attribute, None)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name}: {extractor.__name__}.{attribute} must be a non-empty string")
        if not isinstance(cast(object, extractor.settings), Mapping):
            raise ValueError(f"{name}: {extractor.__name__}.settings must be a mapping")
        patterns: list[object] = list(cast(tuple[object, ...], files)) if isinstance(files, tuple) else []
        if not patterns or not all(isinstance(pattern, str) for pattern in patterns):
            raise ValueError(f"{name}: files must be a tuple of path patterns, such as ('data/papers/*.pdf',)")
        for pattern in cast(list[str], patterns):
            path = PurePosixPath(pattern)
            if not pattern.strip() or path.is_absolute() or ".." in path.parts:
                raise ValueError(f"{name}: {pattern!r} must be a pattern relative to the project root")
        if not isinstance(parallel, int) or isinstance(parallel, bool) or parallel < 1:
            raise ValueError(f"{name}: parallel must be a whole number of at least 1")
