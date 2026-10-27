from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote


SAFE = frozenset("!$&'()*+,;=@-._~")
REFERENCES = frozenset({"fileObject", "fileSet", "containedIn", "sameAs", "key", "field", "references", "parentField"})
COMPRESSIONS = frozenset({".gz", ".bz2", ".xz"})
WORKBOOKS = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel.sheet.macroEnabled.12",
        "application/vnd.ms-excel",
    }
)
MOVED_FROM = "biotope:movedFrom"


def encode(text: str, *, slash: bool = True) -> str:
    return "".join(
        char if char.isalnum() or char in SAFE or (slash and char == "/") else quote(char, safe="")
        for char in unicodedata.normalize("NFC", text)
    )


def file_id(relative: str) -> str:
    return encode(PurePosixPath(relative).as_posix())


def stem(relative: str) -> str:
    name = PurePosixPath(PurePosixPath(relative).name)
    if name.suffix.lower() in COMPRESSIONS:
        name = PurePosixPath(name.stem)
    return name.stem or name.name


def table_id(owner: str, table: str) -> str:
    return f"{owner}#{encode(table, slash=False)}"


def is_kind(entry: dict[str, Any], kind: str) -> bool:
    declared = entry.get("@type")
    return any(str(item).endswith(kind) for item in (declared if isinstance(declared, list) else [declared]))


def _own_id(entry: dict[str, Any]) -> str:
    url = entry.get("contentUrl")
    if is_kind(entry, "FileObject") and isinstance(url, str):
        return file_id(url)
    if is_kind(entry, "FileSet"):
        return encode(str(entry.get("name") or entry["@id"]), slash=False)
    return entry["@id"]


def _named(value: object) -> list[str]:
    items = value if isinstance(value, list) else [value]
    names = [item.get("@id") if isinstance(item, dict) else item for item in items]
    return [name for name in names if isinstance(name, str)]


def includes(entry: dict[str, Any]) -> str:
    return ", ".join(map(str, _named(entry.get("includes"))))


def read_files(record: dict[str, Any], key: str = "field") -> set[str]:
    found: set[str] = set()
    fields = record.get(key)
    for field in [fields] if isinstance(fields, dict) else fields or []:
        source = field.get("source")
        if isinstance(source, dict):
            found.update(name for kind in ("fileObject", "fileSet") for name in _named(source.get(kind)))
        found |= read_files(field, "subField")
    return found


def _base(url: str) -> str:
    return re.escape(re.sub(r"[^A-Za-z0-9_.-]", "_", PurePosixPath(url).stem))


def _inner_name(record: dict[str, Any], url: str) -> str:
    name = str(record.get("name") or record["@id"])
    if name != record["@id"]:
        return name
    matched = re.fullmatch(rf"(?:.+__)?{_base(url)}(?:__\d+)?_(.+?)(?:__\d+)?", name)
    return matched.group(1) if matched else name


def _named_inside(record: dict[str, Any], url: str) -> bool:
    name = str(record.get("name") or record["@id"])
    return not re.fullmatch(rf"(?:.+__)?{_base(url)}(?:__\d+)?", name) and _inner_name(record, url) != name


def _named_after_file(record: dict[str, Any], resource: dict[str, Any], readers: int) -> bool:
    url = resource.get("contentUrl")
    return (
        isinstance(url, str)
        and readers == 1
        and not _named_inside(record, url)
        and WORKBOOKS.isdisjoint(_named(resource.get("encodingFormat")))
    )


def renamer(mapping: dict[str, str]) -> Callable[[str], str]:
    def renamed(value: str) -> str:
        if value in mapping:
            return mapping[value]
        cut = value.rfind("/")
        while cut > 0:
            if value[:cut] in mapping:
                return mapping[value[:cut]] + value[cut:]
            cut = value.rfind("/", 0, cut)
        return value

    return renamed


def rename(metadata: dict[str, Any], mapping: dict[str, str]) -> None:
    renamed = renamer(mapping)

    def visit(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key == "@id" and isinstance(value, str):
                    node[key] = renamed(value)
                elif key in REFERENCES and isinstance(value, str):
                    node[key] = renamed(value)
                elif key in REFERENCES and isinstance(value, list) and all(isinstance(item, str) for item in value):
                    node[key] = [renamed(item) for item in value]
                else:
                    visit(value)

    visit([metadata.get("distribution"), metadata.get("recordSet")])


def stable_ids(metadata: dict[str, Any]) -> None:
    distribution: list[dict[str, Any]] = metadata.get("distribution") or []
    records: list[dict[str, Any]] = metadata.get("recordSet") or []
    records[:] = [record for record in records if record.get("field")]
    resources = {entry["@id"]: entry for entry in distribution if isinstance(entry.get("@id"), str)}
    mapping = {identity: _own_id(entry) for identity, entry in resources.items()}
    readers: Counter[str] = Counter(name for record in records for name in read_files(record))
    for record in records:
        sources = read_files(record) & set(resources)
        if len(sources) != 1 or not isinstance(record.get("@id"), str):
            continue
        [source] = sources
        resource, owner = resources[source], mapping[source]
        if record["@id"].startswith(owner + "#"):
            continue
        url = resource.get("contentUrl")
        if not isinstance(url, str):
            table = str(record.get("name") or record["@id"])
        elif _named_after_file(record, resource, readers[source]):
            table = stem(url)
        else:
            table = _inner_name(record, url)
        mapping[record["@id"]] = table_id(owner, table)
    rename(metadata, mapping)
    check_ids(metadata)
    distribution.sort(key=lambda entry: str(entry.get("@id")))
    records.sort(key=lambda record: str(record.get("@id")))


def check_ids(metadata: dict[str, Any]) -> None:
    distribution: list[dict[str, Any]] = metadata.get("distribution") or []
    records: list[dict[str, Any]] = metadata.get("recordSet") or []
    problems: list[str] = []
    cases: defaultdict[str, set[str]] = defaultdict(set)
    for entry in distribution:
        if is_kind(entry, "FileObject") and isinstance(entry.get("contentUrl"), str):
            cases[unicodedata.normalize("NFC", entry["contentUrl"]).casefold()].add(entry["contentUrl"])
    problems += [
        f"the paths {' and '.join(sorted(paths))} differ only in case" for paths in cases.values() if len(paths) > 1
    ]
    sets: defaultdict[str, list[str]] = defaultdict(list)
    for entry in distribution:
        if is_kind(entry, "FileSet"):
            sets[str(entry.get("name") or entry["@id"])].append(includes(entry))
    problems += [
        f"the file set name {name!r} is used {len(found)} times, by the file sets of {' and '.join(found)}; rename one"
        for name, found in sets.items()
        if len(found) > 1
    ]
    if not problems:
        counts = Counter(item["@id"] for item in [*distribution, *records] if isinstance(item.get("@id"), str))
        problems += [f"{count} entries share the ID {identity!r}" for identity, count in counts.items() if count > 1]
    if problems:
        raise ValueError("cannot give every file and table a stable ID: " + "; ".join(problems))


def moved_ids(metadata: dict[str, Any], old_id: str, old_relative: str, new_relative: str) -> dict[str, str]:
    new_id = file_id(new_relative)
    resource = next((entry for entry in metadata.get("distribution") or [] if entry.get("@id") == old_id), {})
    tables = [record for record in metadata.get("recordSet") or [] if old_id in read_files(record)]
    mapping = {old_id: new_id}
    for record in tables:
        identity = record.get("@id")
        if isinstance(identity, str) and identity.startswith(old_id + "#"):
            table = identity[len(old_id) + 1 :]
            if table == encode(stem(old_relative), slash=False) and _named_after_file(record, resource, len(tables)):
                table = encode(stem(new_relative), slash=False)
            mapping[identity] = f"{new_id}#{table}"
    return mapping


def note_moves(previous: dict[str, Any], current: dict[str, Any]) -> None:
    files = [entry for entry in current.get("distribution") or [] if is_kind(entry, "FileObject")]
    before = {entry.get("@id"): entry for entry in previous.get("distribution") or [] if is_kind(entry, "FileObject")}
    present = {entry.get("@id") for entry in files}
    gone: defaultdict[str, list[str]] = defaultdict(list)
    for identity, entry in before.items():
        if identity not in present and isinstance(identity, str) and entry.get("sha256"):
            gone[entry["sha256"]].append(identity)
    for entry in files:
        old = before.get(entry.get("@id"))
        if old is not None and MOVED_FROM in old:
            entry[MOVED_FROM] = old[MOVED_FROM]
        elif old is None and len(gone.get(entry.get("sha256"), [])) == 1:
            entry[MOVED_FROM] = gone[entry["sha256"]][0]
