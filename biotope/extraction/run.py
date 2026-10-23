from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast, get_type_hints

from pydantic import TypeAdapter, ValidationError

from biotope.extraction.contract import Document, ExtractionError, Extractor
from biotope.extraction.llm import LLMExtractor
from biotope.extraction.loading import load_object
from biotope.extraction.schema import Schema
from biotope.extraction.text import align, convert, page
from biotope.graph.sources import write_text_atomic


TEXTS = Path(".biotope/texts")
STATES = Path(".biotope/extraction")


@dataclass(frozen=True)
class Source:
    path: str
    media_type: str


@dataclass
class Outcome:
    path: str
    status: str
    reason: str = ""
    sha256: str | None = None
    records: int = 0
    moved_from: str | None = None


@dataclass
class Result:
    documents: list[Outcome]
    records: list[dict[str, Any]]
    changed: bool
    unaligned: list[dict[str, Any]] = field(default_factory=lambda: [])
    appeared: list[str] = field(default_factory=lambda: [])
    disappeared: list[str] = field(default_factory=lambda: [])
    moved: list[dict[str, str]] = field(default_factory=lambda: [])


def load_extractor(root: Path, config: dict[str, Any]) -> Extractor:
    options = cast(dict[str, Any], config.get("extraction") or {})
    reference = options.get("extractor")
    if not reference:
        raise ValueError("Set extraction.extractor in .biotope/config.yaml to llm or to path/to/module.py:Class")
    settings = {key: value for key, value in options.items() if key != "extractor"}
    if reference == "llm":
        return LLMExtractor(settings)
    factory = load_object(str(reference), root)
    if not callable(factory):
        raise ValueError(f"{reference!r} is not a class")
    return cast(Extractor, factory(settings))


def identity(extractor: Extractor) -> dict[str, Any]:
    named = {"name": str(extractor.name), "version": str(extractor.version), "settings": dict(extractor.settings)}
    return cast(dict[str, Any], json.loads(json.dumps(named)))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document_text(path: Path, kind: str, digest: str, cache: Path | None) -> str:
    cached = cache / f"{digest}.txt" if cache is not None else None
    if cached is not None and cached.is_file():
        return cached.read_text(encoding="utf-8")
    text = convert(path, kind)
    if cache is not None and cached is not None:
        cache.mkdir(parents=True, exist_ok=True)
        ignore = cache / ".gitignore"
        if not ignore.is_file():
            ignore.write_text("*\n", encoding="utf-8")
        write_text_atomic(cached, text)
    return text


def extract_document(
    extractor: Extractor, schema: Schema, document: Document, provenance: dict[str, Any]
) -> list[dict[str, Any]]:
    raw: object = extractor.extract(document, schema)
    if not isinstance(raw, list):
        raise ExtractionError("the extractor returned no list of records")
    hints = get_type_hints(schema.cls)
    adapters = {entry.name: TypeAdapter[object](hints[entry.name]) for entry in schema.fields}
    records: list[dict[str, Any]] = []
    for index, item in enumerate(cast(list[object], raw), 1):
        values, plain = _values(schema, document, item, index)
        for name, value in plain.items():
            try:
                adapters[name].validate_python(value, strict=True)
            except ValidationError as exc:
                raise ExtractionError(f"record {index}, {name}: {exc.errors()[0]['msg']}") from None
        records.append(finish(schema, document.path, values, provenance))
    for record_id, count in Counter(record["id"] for record in records).items():
        if count > 1:
            key = ", ".join(schema.key) or "none"
            raise ExtractionError(f"{count} records have the ID {record_id}; the record key ({key}) must tell them apart")
    return records


def _values(schema: Schema, document: Document, item: object, index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    names = [entry.name for entry in schema.fields]
    if not isinstance(item, dict) or set(cast(dict[str, Any], item)) != set(names):
        raise ExtractionError(f"record {index} does not have exactly the fields {', '.join(names)}")
    given = cast(dict[str, Any], item)
    values: dict[str, Any] = {}
    plain: dict[str, Any] = {}
    for entry in schema.fields:
        if entry.many:
            if not isinstance(given[entry.name], list):
                raise ExtractionError(f"record {index}, {entry.name}: expected a list")
            items = [_evidenced(document, entry.name, part, index) for part in cast(list[object], given[entry.name])]
            values[entry.name] = items
            plain[entry.name] = [part["value"] for part in items]
        else:
            values[entry.name] = _evidenced(document, entry.name, given[entry.name], index)
            plain[entry.name] = values[entry.name]["value"]
    return values, plain


def _evidenced(document: Document, name: str, given: object, index: int) -> dict[str, Any]:
    if not isinstance(given, dict) or "value" not in given:
        raise ExtractionError(f"record {index}, {name}: expected an object with a value and its quote or locator")
    entry = cast(dict[str, Any], given)
    value, quote, locator = entry["value"], entry.get("quote"), entry.get("locator")
    if locator is not None:
        evidence = {"quote": None, "locator": str(locator), "aligned": None, "start": None, "end": None, "page": None}
    elif value is None and not quote:
        evidence = None
    else:
        text = quote if isinstance(quote, str) and quote.strip() else None
        span = align(document.text, text) if text else None
        evidence = {
            "quote": text,
            "locator": None,
            "aligned": span is not None,
            "start": span[0] if span else None,
            "end": span[1] if span else None,
            "page": page(document.text, document.media_type, span[0]) if span else None,
        }
    return {"value": value, "evidence": evidence}


def record_id(schema: Schema, path: str, values: dict[str, Any]) -> str:
    if not schema.key:
        return path
    parts = (f"{name}={json.dumps(values[name]['value'], ensure_ascii=False)}" for name in schema.key)
    return f"{path}#{';'.join(parts)}"


def finish(schema: Schema, path: str, values: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    return {"id": record_id(schema, path, values), "document": path, "values": values, "provenance": provenance}


def unaligned(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for record in records:
        for name, given in record["values"].items():
            for item in given if isinstance(given, list) else [given]:
                evidence = item["evidence"]
                if item["value"] is not None and evidence is not None and evidence["aligned"] is False:
                    found.append({"record": record["id"], "field": name, "quote": evidence["quote"]})
    return found


def run(
    root: Path, schema: Schema, extractor: Extractor, sources: list[Source], output: Path, state_path: Path
) -> Result:
    previous_state = cast(dict[str, Any], _read_json(state_path).get("documents", {}))
    previous = _read_records(output)
    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in previous:
        by_document[record["document"]].append(record)
    stamp = {"schema_revision": schema.revision, "extractor": identity(extractor)}
    registered = {source.path for source in sources}
    state: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    outcomes: list[Outcome] = []
    moved: list[dict[str, str]] = []
    for source in sources:
        file = root / source.path
        kept = by_document.get(source.path, [])
        if not file.is_file():
            if source.path in previous_state:
                state[source.path] = previous_state[source.path]
                records += kept
            outcomes.append(Outcome(source.path, "missing", "the file does not exist", records=len(kept)))
            continue
        digest = sha256(file)
        wanted = {"sha256": digest, **stamp}
        origin = _origin(source.path, wanted, previous_state, registered)
        if origin is not None:
            reused = [finish(schema, source.path, record["values"], record["provenance"]) for record in by_document[origin]]
            relocated = origin != source.path and origin not in registered
            if relocated:
                moved += [{"from": old["id"], "to": new["id"]} for old, new in zip(by_document[origin], reused)]
            state[source.path] = wanted
            records += reused
            outcomes.append(
                Outcome(source.path, "reused", sha256=digest, records=len(reused), moved_from=origin if relocated else None)
            )
            continue
        provenance = {"document_sha256": digest, "media_type": source.media_type, "schema": schema.name, **stamp}
        try:
            text = document_text(file, source.media_type, digest, root / TEXTS)
            extracted = extract_document(
                extractor, schema, Document(source.path, digest, source.media_type, text), provenance
            )
        except Exception as exc:
            reason = str(exc) if isinstance(exc, ExtractionError) else f"{type(exc).__name__}: {exc}"
            if source.path in previous_state:
                state[source.path] = previous_state[source.path]
                records += kept
            outcomes.append(Outcome(source.path, "failed", reason, digest, len(kept)))
            continue
        state[source.path] = wanted
        records += extracted
        outcomes.append(Outcome(source.path, "extracted", sha256=digest, records=len(extracted)))
    records.sort(key=lambda record: record["id"])
    old = {record["id"] for record in previous}
    new = {record["id"] for record in records}
    changed = _write(output, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    _write(state_path, json.dumps({"schema": schema.name, "documents": dict(sorted(state.items()))}, indent=2) + "\n")
    return Result(
        outcomes,
        records,
        changed,
        unaligned(records),
        sorted(new - old - {pair["to"] for pair in moved}),
        sorted(old - new - {pair["from"] for pair in moved}),
        moved,
    )


def _origin(path: str, wanted: dict[str, Any], previous: dict[str, Any], registered: set[str]) -> str | None:
    if previous.get(path) == wanted:
        return path
    matches = [other for other, entry in previous.items() if entry == wanted]
    return next((other for other in matches if other not in registered), matches[0] if matches else None)


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else {}


def _read_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [cast(dict[str, Any], json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write(path: Path, text: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    write_text_atomic(path, text)
    return True
