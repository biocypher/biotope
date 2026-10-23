from __future__ import annotations

import hashlib
import json
import threading
from collections import Counter, defaultdict
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast, get_type_hints

from pydantic import TypeAdapter, ValidationError

from biotope.extraction.contract import Document, ExtractionError, Extractor
from biotope.extraction.llm import LLMExtractor
from biotope.extraction.loading import load_object
from biotope.extraction.schema import Schema
from biotope.extraction.text import CONVERSION, Searchable, convert, page, squeeze
from biotope.graph.sources import write_text_atomic


TEXTS = Path(".biotope/texts")
STATES = Path(".biotope/extraction")
PARALLEL = 4
SHORT = 10
DISTINCTIVE = 30


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
    appeared: list[str] = field(default_factory=lambda: [])
    disappeared: list[str] = field(default_factory=lambda: [])
    moved: list[dict[str, str]] = field(default_factory=lambda: [])


def load_extractor(root: Path, config: dict[str, Any]) -> Extractor:
    options = cast(dict[str, Any], config.get("extraction") or {})
    reference = options.get("extractor")
    if not reference:
        raise ValueError("Set extraction.extractor in .biotope/config.yaml to llm or to path/to/module.py:Class")
    settings = {key: value for key, value in options.items() if key not in {"extractor", "parallel"}}
    if reference == "llm":
        return LLMExtractor(settings)
    factory = load_object(str(reference), root)
    if not callable(factory):
        raise ValueError(f"{reference!r} is not a class")
    return cast(Extractor, factory(settings))


def parallelism(config: dict[str, Any]) -> int:
    options = cast(dict[str, Any], config.get("extraction") or {})
    parallel = options.get("parallel", PARALLEL)
    if not isinstance(parallel, int) or isinstance(parallel, bool) or parallel < 1:
        raise ValueError("Set extraction.parallel in .biotope/config.yaml to a whole number of at least 1")
    return parallel


def identity(extractor: Extractor) -> dict[str, Any]:
    named = {"name": str(extractor.name), "version": str(extractor.version), "settings": dict(extractor.settings)}
    return cast(dict[str, Any], json.loads(json.dumps(named)))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document_text(path: Path, kind: str, digest: str, cache: Path | None) -> str:
    cached = cache / f"{digest}-{CONVERSION}.txt" if cache is not None else None
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


def extract_all(
    extractor: Extractor,
    schema: Schema,
    root: Path,
    work: list[tuple[int, Source]],
    total: int,
    cache: Path | None,
    redo: frozenset[str],
    parallel: int,
    announce: Callable[[int, int, str], None],
) -> list[list[dict[str, Any]] | BaseException]:
    slots = threading.Semaphore(parallel)
    pending: list[Future[list[dict[str, Any]]] | BaseException] = []
    with ThreadPoolExecutor(parallel) as pool:
        for number, source in work:
            slots.acquire()
            announce(number, total, source.path)
            try:
                document, provenance = _prepare(extractor, schema, root, source, cache, source.path in redo)
            except Exception as exc:
                slots.release()
                pending.append(exc)
                continue
            future = pool.submit(_extract_document, extractor, schema, document, provenance)
            future.add_done_callback(lambda _: slots.release())
            pending.append(future)
    return [item if isinstance(item, BaseException) else item.exception() or item.result() for item in pending]


def failure(exc: BaseException) -> str:
    return str(exc) if isinstance(exc, ExtractionError) else f"{type(exc).__name__}: {exc}"


def _prepare(
    extractor: Extractor, schema: Schema, root: Path, source: Source, cache: Path | None, redone: bool
) -> tuple[Document, dict[str, Any]]:
    file = root / source.path
    digest = sha256(file)
    provenance: dict[str, Any] = {
        "document_sha256": digest,
        "media_type": source.media_type,
        "schema": schema.name,
        "schema_revision": schema.revision,
        "extractor": identity(extractor),
    }
    if redone:
        provenance["redone"] = True
    text = document_text(file, source.media_type, digest, cache)
    return Document(source.path, digest, source.media_type, text), provenance


def _extract_document(
    extractor: Extractor, schema: Schema, document: Document, provenance: dict[str, Any]
) -> list[dict[str, Any]]:
    raw = cast(object, extractor.extract(document, schema))
    if not isinstance(raw, list):
        raise ExtractionError("the extractor returned no list of records")
    hints = get_type_hints(schema.cls)
    adapters = {entry.name: TypeAdapter[object](hints[entry.name]) for entry in schema.fields}
    searchable = Searchable(document.text)
    records: list[dict[str, Any]] = []
    for index, item in enumerate(cast(list[object], raw), 1):
        values, plain = _values(schema, document, searchable, item, index)
        for name, value in plain.items():
            try:
                validated = adapters[name].validate_python(value, strict=True)
            except ValidationError as exc:
                raise ExtractionError(f"record {index}, {name}: {exc.errors()[0]['msg']}") from None
            given = values[name]
            parts = cast(list[dict[str, Any]], given if isinstance(given, list) else [given])
            normals = cast(list[object], validated if isinstance(given, list) else [validated])
            for part, normal in zip(parts, normals):
                part["value"] = normal
        records.append(finish(schema, document.path, values, provenance))
    for record_id, count in Counter(record["id"] for record in records).items():
        if count > 1:
            key = ", ".join(schema.key) or "none"
            raise ExtractionError(
                f"{count} records have the ID {record_id}; the record key ({key}) must tell them apart"
            )
    return records


def _values(
    schema: Schema, document: Document, searchable: Searchable, item: object, index: int
) -> tuple[dict[str, Any], dict[str, Any]]:
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
            items = [
                _evidenced(document, searchable, entry.name, part, index)
                for part in cast(list[object], given[entry.name])
            ]
            values[entry.name] = items
            plain[entry.name] = [part["value"] for part in items]
        else:
            values[entry.name] = _evidenced(document, searchable, entry.name, given[entry.name], index)
            plain[entry.name] = values[entry.name]["value"]
    return values, plain


def _evidenced(document: Document, searchable: Searchable, name: str, given: object, index: int) -> dict[str, Any]:
    if not isinstance(given, dict) or "value" not in given:
        raise ExtractionError(f"record {index}, {name}: expected an object with a value and its quote or locator")
    entry = cast(dict[str, Any], given)
    value, quote, locator = entry["value"], entry.get("quote"), entry.get("locator")
    text = quote if isinstance(quote, str) and quote.strip() else None
    evidence: dict[str, Any] | None = None
    if locator is not None:
        evidence = dict.fromkeys(("quote", "locator", "aligned", "start", "end", "page", "occurrences", "weak"))
        evidence["locator"] = str(locator)
    elif text is not None:
        span = searchable.align(text)
        occurrences = searchable.count(text)
        evidence = {
            "quote": text,
            "locator": None,
            "aligned": span is not None,
            "start": span[0] if span else None,
            "end": span[1] if span else None,
            "page": page(document.text, document.media_type, span[0]) if span else None,
            "occurrences": occurrences,
            "weak": bool(weaknesses(text, occurrences)) if span else None,
        }
    return {"value": value, "evidence": evidence}


def weaknesses(quote: str, occurrences: int) -> list[str]:
    length = len(squeeze(quote))
    found = (("short", length < SHORT), ("repeated", occurrences > 1 and length < DISTINCTIVE))
    return [reason for reason, weak in found if weak]


def record_id(schema: Schema, path: str, values: dict[str, Any]) -> str:
    if not schema.key:
        return path
    parts = (f"{name}={json.dumps(values[name]['value'], ensure_ascii=False)}" for name in schema.key)
    return f"{path}#{';'.join(parts)}"


def finish(schema: Schema, path: str, values: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    total, unaligned = support(values)
    return {
        "id": record_id(schema, path, values),
        "document": path,
        "supported": unaligned * 2 <= total,
        "values": values,
        "provenance": provenance,
    }


def evidenced_values(values: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (name, item)
        for name, given in values.items()
        for item in cast(list[dict[str, Any]], given if isinstance(given, list) else [given])
        if item["value"] is not None
    ]


def unaligned(item: dict[str, Any]) -> bool:
    return item["evidence"] is None or item["evidence"]["aligned"] is False


def support(values: dict[str, Any]) -> tuple[int, int]:
    found = evidenced_values(values)
    return len(found), sum(unaligned(item) for _, item in found)


def unsupported_reason(records: list[dict[str, Any]]) -> str:
    count = sum(not record["supported"] for record in records)
    if not count:
        return ""
    return (
        f"{count} of {len(records)} records unsupported: most of their values have no aligned evidence, "
        "so the extractor may have answered from memory"
    )


@dataclass
class Review:
    unaligned: list[dict[str, Any]] = field(default_factory=lambda: [])
    weak: list[dict[str, Any]] = field(default_factory=lambda: [])
    unsupported: list[dict[str, Any]] = field(default_factory=lambda: [])
    counts: Counter[str] = field(default_factory=lambda: Counter(values=0, aligned=0, unaligned=0, weak=0))


def review(records: list[dict[str, Any]]) -> Review:
    found = Review()
    for record in records:
        if not record["supported"]:
            total, missing = support(record["values"])
            found.unsupported.append({"record": record["id"], "values": total, "unaligned": missing})
        for name, item in evidenced_values(record["values"]):
            evidence = item["evidence"]
            found.counts["values"] += 1
            where = {"record": record["id"], "field": name, "quote": evidence and evidence["quote"]}
            if unaligned(item):
                found.unaligned.append(where)
                found.counts["unaligned"] += 1
                continue
            found.counts["aligned"] += bool(evidence["aligned"])
            if evidence.get("weak"):
                found.weak.append({**where, "reasons": weaknesses(evidence["quote"], evidence["occurrences"])})
                found.counts["weak"] += 1
    return found


def run(
    root: Path,
    schema: Schema,
    extractor: Extractor,
    sources: list[Source],
    output: Path,
    state_path: Path,
    redo: frozenset[str] = frozenset(),
    announce: Callable[[int, int, str], None] = lambda index, total, path: None,
    parallel: int = 1,
) -> Result:
    previous = _read_records(output)
    previous_state = cast(dict[str, Any], _read_json(state_path).get("documents", {})) if output.is_file() else {}
    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in previous:
        by_document[record["document"]].append(record)
    stamp = {"schema_revision": schema.revision, "extractor": identity(extractor)}
    registered = {source.path for source in sources}
    state: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    outcomes: list[Outcome] = []
    moved: list[dict[str, str]] = []
    claimed: set[str] = set()
    work: list[tuple[int, Source]] = []
    waiting: list[tuple[int, str, list[dict[str, Any]]]] = []
    for number, source in enumerate(sources, 1):
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
        origin = None if source.path in redo else _origin(source.path, wanted, previous_state, registered | claimed)
        if origin is not None:
            reused = [
                finish(schema, source.path, record["values"], record["provenance"]) for record in by_document[origin]
            ]
            relocated = origin != source.path and origin not in registered | claimed
            claimed.add(origin)
            if relocated:
                moved += [{"from": old["id"], "to": new["id"]} for old, new in zip(by_document[origin], reused)]
            state[source.path] = wanted
            records += reused
            outcomes.append(
                Outcome(
                    source.path, "reused", sha256=digest, records=len(reused), moved_from=origin if relocated else None
                )
            )
            continue
        work.append((number, source))
        waiting.append((len(outcomes), digest, kept))
        outcomes.append(Outcome(source.path, "extracted", sha256=digest))
    done = extract_all(extractor, schema, root, work, len(sources), root / TEXTS, redo, parallel, announce)
    for (position, digest, kept), extracted in zip(waiting, done):
        path = outcomes[position].path
        if isinstance(extracted, BaseException):
            if path in previous_state:
                state[path] = previous_state[path]
                records += kept
            outcomes[position] = Outcome(path, "failed", failure(extracted), digest, len(kept))
            continue
        state[path] = {"sha256": digest, **stamp}
        records += extracted
        reason = unsupported_reason(extracted)
        status = "unsupported" if reason else "extracted" if extracted else "empty"
        outcomes[position] = Outcome(path, status, reason, digest, len(extracted))
    records.sort(key=lambda record: record["id"])
    old = {record["id"] for record in previous}
    new = {record["id"] for record in records}
    changed = _write(output, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    _write(state_path, json.dumps({"schema": schema.name, "documents": dict(sorted(state.items()))}, indent=2) + "\n")
    return Result(
        outcomes,
        records,
        changed,
        sorted(new - old - {pair["to"] for pair in moved}),
        sorted(old - new - {pair["from"] for pair in moved}),
        moved,
    )


def _origin(path: str, wanted: dict[str, Any], previous: dict[str, Any], taken: set[str]) -> str | None:
    if previous.get(path) == wanted:
        return path
    matches = [other for other, entry in previous.items() if entry == wanted]
    free = [other for other in matches if other not in taken]
    return max(free or matches, key=lambda other: _shared_tail(path, other), default=None)


def _shared_tail(path: str, other: str) -> int:
    count = 0
    for mine, theirs in zip(reversed(path.split("/")), reversed(other.split("/"))):
        if mine != theirs:
            break
        count += 1
    return count


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
