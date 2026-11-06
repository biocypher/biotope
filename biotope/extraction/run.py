from __future__ import annotations

import filecmp
import hashlib
import inspect
import json
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast, get_type_hints

from pydantic import TypeAdapter, ValidationError

from biotope.croissant import annotation
from biotope.extraction.contract import Document, Extraction, ExtractionError, Extractor
from biotope.extraction.schema import Schema
from biotope.graph.discovery import is_placeholder
from biotope.graph.sources import refresh_description, write_text_atomic
from biotope.metadata import FILE_OBJECT_TYPE, dataset_dir_for_manifest, dataset_id, manifest_for, resolve_content_url


PROGRESS = Path(".biotope/progress")
RECORDS = Path("data/extracted")
BASED_ON = "isBasedOn"
SCHEMA_REVISION = "biotope:schemaRevision"
EXTRACTOR = "biotope:extractor"


def records_path(root: Path, name: str) -> Path:
    return root / RECORDS / f"{name}.jsonl"


def progress_path(root: Path, name: str) -> Path:
    return root / PROGRESS / f"{name}.jsonl"


def records_files(root: Path) -> set[Path]:
    return set((root / RECORDS).glob("*.jsonl"))


def records_entry(root: Path, target: Path, metadata: dict[str, Any]) -> dict[str, Any] | None:
    relative = target.relative_to(root).as_posix()
    entries = cast(list[dict[str, Any]], metadata.get("distribution", []))
    return next(
        (entry for entry in entries if entry.get("@type") == FILE_OBJECT_TYPE and entry.get("contentUrl") == relative),
        None,
    )


def extracted_files(root: Path) -> set[str]:
    return {document["contentUrl"] for path in records_files(root) for document in _read(_described(root, path))}


def described_origin(documents: list[Outcome], schema: Schema, extractor: dict[str, Any]) -> dict[str, Any]:
    read = [
        {"contentUrl": outcome.path} | ({} if outcome.status == "failed" else {"sha256": outcome.sha256})
        for outcome in sorted(documents, key=lambda outcome: outcome.path)
    ]
    return {BASED_ON: read, SCHEMA_REVISION: schema.revision, EXTRACTOR: extractor}


def forget(root: Path, records_file: Path) -> None:
    if records_file.resolve() in {path.resolve() for path in records_files(root)}:
        progress_path(root, records_file.stem).unlink(missing_ok=True)


def placeholders(extraction: Extraction) -> list[Path]:
    files = {Path(inspect.getfile(item)) for item in (extraction.schema, extraction.extractor)}
    return sorted(path for path in files if is_placeholder(path))


@dataclass(frozen=True)
class Source:
    path: str
    record_path: str
    dataset: str


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
    appeared: list[str] = field(default_factory=lambda: [])
    disappeared: list[str] = field(default_factory=lambda: [])
    moved: list[dict[str, str]] = field(default_factory=lambda: [])


def identity(extractor: type[Extractor]) -> dict[str, Any]:
    named = {"name": str(extractor.name), "version": str(extractor.version), "settings": dict(extractor.settings)}
    return cast(dict[str, Any], json.loads(json.dumps(named)))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def described_files(root: Path) -> dict[str, Source]:
    found: dict[str, Source] = {}
    for manifest in sorted((root / ".biotope/datasets").rglob("*.jsonld")):
        dataset = dataset_id(manifest, root)
        data = (root / dataset).resolve()
        dataset_dir = dataset_dir_for_manifest(manifest, root)
        for entry in cast(list[dict[str, Any]], refresh_description(manifest).get("distribution") or []):
            url = entry.get("contentUrl")
            if entry.get("@type") != FILE_OBJECT_TYPE or not isinstance(url, str):
                continue
            located = resolve_content_url(url, dataset_dir, root)
            if located is None:
                continue
            located = located.resolve()
            within = located.relative_to(data).as_posix() if data.is_dir() else ""
            record_path = f"{data.name}/{within}" if within else data.name
            path = located.relative_to(root.resolve()).as_posix()
            found.setdefault(path, Source(path, record_path, dataset))
    return found


def matched_files(root: Path, extraction: Extraction) -> list[str]:
    found: set[str] = set()
    for pattern in extraction.files:
        matched = {path.relative_to(root) for path in root.glob(pattern) if path.is_file()}
        documents = {
            relative.as_posix()
            for relative in matched
            if not any(part.startswith(".") for part in relative.parts)
            and not relative.name.endswith(annotation.SUFFIX)
        }
        if not documents:
            raise ValueError(f"{extraction.name}: {pattern} matches no file")
        found |= documents
    return sorted(found)


def sources(root: Path, extraction: Extraction, described: dict[str, Source]) -> list[Source]:
    paths = matched_files(root, extraction)
    undescribed = [path for path in paths if path not in described]
    if undescribed:
        originals = {path: _original(root, path, described) for path in undescribed}
        others = [path for path, original in originals.items() if original is None]
        problems = [
            f"{path} is identical to {original}, and biotope add describes identical files once, so delete the copy"
            for path, original in originals.items()
            if original is not None
        ]
        if others:
            them = "it" if len(others) == 1 else "them"
            problems.insert(0, f"no dataset describes {', '.join(others)}; describe {them} with biotope add")
        raise ValueError(f"{extraction.name}: {'; '.join(problems)}, or narrow the extraction's file patterns")
    found = [described[path] for path in paths]
    sharing: dict[str, list[str]] = defaultdict(list)
    for source in found:
        sharing[source.record_path].append(source.path)
    shared = [
        f"{', '.join(files)} would share the record path {path}" for path, files in sharing.items() if len(files) > 1
    ]
    if shared:
        raise ValueError(
            f"{extraction.name}: {'; '.join(shared)}. A record path starts with the name of the document's dataset "
            "folder or file, so give the datasets different names"
        )
    return found


def _original(root: Path, path: str, described: dict[str, Source]) -> str | None:
    return next(
        (
            other
            for other in sorted(described)
            if (root / other).is_file() and filecmp.cmp(root / path, root / other, shallow=False)
        ),
        None,
    )


def extract_all(
    extraction: Extraction,
    schema: Schema,
    root: Path,
    work: list[tuple[int, Source]],
    total: int,
    announce: Callable[[int, int, str], None],
) -> Iterator[tuple[int, list[dict[str, Any]] | BaseException]]:
    if not work:
        return
    try:
        extractor = extraction.extractor()
    except Exception as exc:
        for position in range(len(work)):
            yield position, exc
        return
    running: dict[Future[list[dict[str, Any]]], int] = {}
    with ThreadPoolExecutor(extraction.parallel) as pool:
        for position, (number, source) in enumerate(work):
            if len(running) == extraction.parallel:
                yield from _finished(running)
            announce(number, total, source.path)
            try:
                document, provenance = _prepare(extraction, schema, root, source)
            except Exception as exc:
                yield position, exc
                continue
            running[pool.submit(_extract_document, extractor, schema, document, source, provenance)] = position
        while running:
            yield from _finished(running)


def _finished(
    running: dict[Future[list[dict[str, Any]]], int],
) -> Iterator[tuple[int, list[dict[str, Any]] | BaseException]]:
    done, _ = wait(running, return_when=FIRST_COMPLETED)
    for future in done:
        yield running.pop(future), future.exception() or future.result()


def failure(exc: BaseException) -> str:
    return str(exc) if isinstance(exc, ExtractionError) else f"{type(exc).__name__}: {exc}"


def document_status(records: list[dict[str, Any]]) -> str:
    return "extracted" if records else "empty"


def _prepare(extraction: Extraction, schema: Schema, root: Path, source: Source) -> tuple[Document, dict[str, Any]]:
    file = root / source.path
    digest = sha256(file)
    provenance: dict[str, Any] = {
        "document_sha256": digest,
        "schema": schema.name,
        "schema_revision": schema.revision,
        "extractor": identity(extraction.extractor),
    }
    return Document(file.resolve(), digest), provenance


def _extract_document(
    extractor: Extractor, schema: Schema, document: Document, source: Source, provenance: dict[str, Any]
) -> list[dict[str, Any]]:
    raw = cast(object, extractor.extract(document, schema))
    if not isinstance(raw, list):
        raise ExtractionError("the extractor returned no list of records")
    hints = get_type_hints(schema.cls)
    adapters = {entry.name: TypeAdapter[object](hints[entry.name]) for entry in schema.fields}
    records: list[dict[str, Any]] = []
    for index, item in enumerate(cast(list[object], raw), 1):
        values, plain = _values(schema, item, index)
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
        records.append(finish(schema, source, values, provenance))
    for record_id, count in Counter(record["id"] for record in records).items():
        if count > 1:
            key = ", ".join(schema.key) or "none"
            raise ExtractionError(
                f"{count} records have the ID {record_id}; the record key ({key}) must tell them apart"
            )
    return records


def _values(schema: Schema, item: object, index: int) -> tuple[dict[str, Any], dict[str, Any]]:
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
            items = [_evidenced(entry.name, part, index) for part in cast(list[object], given[entry.name])]
            values[entry.name] = items
            plain[entry.name] = [part["value"] for part in items]
        else:
            values[entry.name] = _evidenced(entry.name, given[entry.name], index)
            plain[entry.name] = values[entry.name]["value"]
    return values, plain


def _evidenced(name: str, given: object, index: int) -> dict[str, Any]:
    if not isinstance(given, dict) or "value" not in given:
        raise ExtractionError(f"record {index}, {name}: expected an object with a value and its quote or locator")
    entry = cast(dict[str, Any], given)
    unknown = sorted(set(entry) - {"value", "quote", "locator"})
    if unknown:
        raise ExtractionError(f"record {index}, {name}: unknown keys {', '.join(unknown)}")
    evidence = {key: entry.get(key) for key in ("quote", "locator")}
    for key, text in evidence.items():
        if text is not None and not isinstance(text, str):
            raise ExtractionError(f"record {index}, {name}: the {key} must be a string")
    kept = {key: text if isinstance(text, str) and text.strip() else None for key, text in evidence.items()}
    return {"value": entry["value"], "evidence": kept if any(kept.values()) else None}


def record_id(schema: Schema, record_path: str, values: dict[str, Any]) -> str:
    if not schema.key:
        return record_path
    parts = (f"{name}={json.dumps(values[name]['value'], ensure_ascii=False)}" for name in schema.key)
    return f"{record_path}#{';'.join(parts)}"


def finish(schema: Schema, source: Source, values: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record_id(schema, source.record_path, values),
        "document": source.path,
        "values": values,
        "provenance": provenance,
    }


def run(
    root: Path,
    extraction: Extraction,
    schema: Schema,
    found: list[Source],
    redo: frozenset[str] = frozenset(),
    announce: Callable[[int, int, str], None] = lambda index, total, path: None,
) -> Result:
    output = records_path(root, extraction.name)
    progress = progress_path(root, extraction.name)
    previous = _read_records(output)
    previous_state = _described_state(_described(root, output)) if output.is_file() else {}
    previous_state.update({record["document"]: _stamp(record["provenance"]) for record in previous})
    by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in previous:
        by_document[record["document"]].append(record)
    for finished in _finished_documents(progress):
        by_document[finished["document"]] = finished["records"]
        previous_state[finished["document"]] = finished["state"]
    stamp = {"schema_revision": schema.revision, "extractor": identity(extraction.extractor)}
    registered = {source.path for source in found}
    records: list[dict[str, Any]] = []
    outcomes: list[Outcome] = []
    moved: list[dict[str, str]] = []
    claimed: set[str] = set()
    work: list[tuple[int, Source]] = []
    waiting: list[tuple[int, str]] = []

    def keep(path: str) -> int:
        kept = by_document.get(path, [])
        records.extend(kept)
        return len(kept)

    for number, source in enumerate(found, 1):
        try:
            digest = sha256(root / source.path)
        except Exception as exc:
            outcomes.append(Outcome(source.path, "failed", failure(exc), records=keep(source.path)))
            continue
        wanted = {"sha256": digest, **stamp}
        origin = None if source.path in redo else _origin(source.path, wanted, previous_state, registered | claimed)
        if origin is not None:
            reused = [finish(schema, source, record["values"], record["provenance"]) for record in by_document[origin]]
            relocated = origin != source.path and origin not in registered | claimed
            claimed.add(origin)
            if relocated:
                pairs = zip(by_document[origin], reused)
                moved += [{"from": old["id"], "to": new["id"]} for old, new in pairs if old["id"] != new["id"]]
            records += reused
            outcomes.append(
                Outcome(
                    source.path, "reused", sha256=digest, records=len(reused), moved_from=origin if relocated else None
                )
            )
            continue
        work.append((number, source))
        waiting.append((len(outcomes), digest))
        outcomes.append(Outcome(source.path, "extracted", sha256=digest))
    for index, extracted in extract_all(extraction, schema, root, work, len(found), announce):
        position, digest = waiting[index]
        path = outcomes[position].path
        if isinstance(extracted, BaseException):
            outcomes[position] = Outcome(path, "failed", failure(extracted), digest, keep(path))
            continue
        _remember(root, progress, path, {"sha256": digest, **stamp}, extracted)
        records += extracted
        outcomes[position] = Outcome(path, document_status(extracted), "", digest, len(extracted))
    records.sort(key=lambda record: record["id"])
    old = {record["id"] for record in previous}
    new = {record["id"] for record in records}
    _write(output, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    progress.unlink(missing_ok=True)
    return Result(
        outcomes,
        records,
        sorted(new - old - {pair["to"] for pair in moved}),
        sorted(old - new - {pair["from"] for pair in moved}),
        moved,
    )


def _described(root: Path, records: Path) -> dict[str, Any]:
    return records_entry(root, records, _read_json(manifest_for(records, root))) or {}


def _read(described: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], described.get(BASED_ON, []))


def _described_state(described: dict[str, Any]) -> dict[str, Any]:
    stamp = {"schema_revision": described.get(SCHEMA_REVISION), "extractor": described.get(EXTRACTOR)}
    return {
        document["contentUrl"]: {"sha256": document["sha256"], **stamp}
        for document in _read(described)
        if "sha256" in document
    }


def _stamp(provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "sha256": provenance["document_sha256"],
        "schema_revision": provenance["schema_revision"],
        "extractor": provenance["extractor"],
    }


def _ignored_directory(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    ignore = directory / ".gitignore"
    if not ignore.is_file():
        ignore.write_text("*\n", encoding="utf-8")


def _remember(root: Path, progress: Path, path: str, state: dict[str, Any], records: list[dict[str, Any]]) -> None:
    _ignored_directory(root / PROGRESS)
    with progress.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"document": path, "state": state, "records": records}, ensure_ascii=False) + "\n")


def _finished_documents(progress: Path) -> Iterator[dict[str, Any]]:
    if not progress.is_file():
        return
    for line in progress.read_text(encoding="utf-8").splitlines():
        try:
            yield cast(dict[str, Any], json.loads(line))
        except ValueError:
            continue


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


def _write(path: Path, text: str) -> None:
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        write_text_atomic(path, text)
