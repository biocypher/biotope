from __future__ import annotations

import copy
import io
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.util import load_yaml_guess_indent

from biotope.croissant.ids import is_kind, stable_ids


FOLDER_FILE = ".biotope.yaml"
SUFFIX = ".biotope.yaml"
FROM_DATA = "biotope:fromData"
TABLES = "tables"
COLUMNS = "columns"
FILE_SETS = "file_sets"
KEY = "key"
HEADER = "# What people write about this dataset. A value here wins over the data's; an empty value clears it.\n"


def annotation_path(data: Path) -> Path:
    return data / FOLDER_FILE if data.is_dir() else data.with_name(data.name + SUFFIX)


def located(manifest: Path, description: Mapping[str, Any]) -> Path | None:
    parts = manifest.resolve().parts
    places = [index for index in range(len(parts) - 1) if parts[index : index + 2] == (".biotope", "datasets")]
    if not places:
        return None
    root, relative = Path(*parts[: places[-1]]), Path(*parts[places[-1] + 2 :]).with_suffix("")
    if (root / relative).is_dir():
        return root / relative / FOLDER_FILE
    urls = [
        entry["contentUrl"]
        for entry in description.get("distribution") or []
        if is_kind(entry, "FileObject") and isinstance(entry.get("contentUrl"), str) and "containedIn" not in entry
    ]
    return root / f"{urls[0]}{SUFFIX}" if urls else None


def read(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        loaded = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML: {exc}") from exc
    if loaded is not None and not isinstance(loaded, dict):
        raise ValueError(f"{path}: an annotation file holds a mapping")
    return loaded or {}


def current(description: Mapping[str, Any], annotation: Mapping[str, Any]) -> dict[str, Any]:
    data = restored(description)
    renamed = any(
        is_kind(entry, "FileSet") and "name" in (entry.get(FROM_DATA) or {})
        for entry in description.get("distribution") or []
    )
    given_names = _mapping(annotation.get(FILE_SETS))
    for entry in data.get("distribution") or []:
        if is_kind(entry, "FileSet") and entry.get("name") in given_names:
            _put(entry, "name", given_names[entry["name"]])
            renamed = True
    if renamed:
        stable_ids(data)
    for key, value in annotation.items():
        if key not in (TABLES, FILE_SETS):
            _put(data, key, _creators(value) if key == "creator" else value)
    records = {record.get("@id"): record for record in data.get("recordSet") or []}
    for identity, given in _mapping(annotation.get(TABLES)).items():
        record = records.get(identity)
        if record is None:
            continue
        fields = columns(record)
        for key, value in _mapping(given).items():
            if key == COLUMNS:
                for name, values in _mapping(value).items():
                    for field_key, field_value in _mapping(values).items() if name in fields else ():
                        _put(fields[name], field_key, field_value)
            elif key == KEY:
                if _empty(value) or _key(value, fields):
                    _put(record, KEY, _key(value, fields))
            else:
                _put(record, key, value)
    return data


def restored(description: Mapping[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(dict(description))
    for item in _items(data):
        for key, value in (item.pop(FROM_DATA, None) or {}).items():
            if value is None:
                item.pop(key, None)
            else:
                item[key] = value
    return data


def unknown(description: Mapping[str, Any], annotation: Mapping[str, Any]) -> list[str]:
    files = {
        entry.get("name") for entry in restored(description).get("distribution") or [] if is_kind(entry, "FileSet")
    }
    found = [f"file set {name!r}" for name in _mapping(annotation.get(FILE_SETS)) if name not in files]
    records = {record.get("@id"): record for record in current(description, annotation).get("recordSet") or []}
    for identity, given in _mapping(annotation.get(TABLES)).items():
        if identity not in records:
            found.append(f"table {identity!r}")
            continue
        fields = columns(records[identity])
        named = [*_mapping(_mapping(given).get(COLUMNS)), *names(_mapping(given).get(KEY))]
        found += [f"column {name!r} of {identity!r}" for name in dict.fromkeys(named) if name not in fields]
    return found


def edited(path: Path, scope: Sequence[str], values: Mapping[str, Any]) -> str:
    text = path.read_text(encoding="utf-8") if path.is_file() else HEADER

    def change(document: CommentedMap) -> None:
        target = document
        for name in scope:
            if not isinstance(target.get(name), dict):
                target[name] = CommentedMap()
            target = target[name]
        for key, value in values.items():
            target[key] = None if _empty(value) else value

    return _rewritten(path, text, change)


def renamed(path: Path, rename: Callable[[str], str]) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    tables = _mapping(_mapping(YAML(typ="safe").load(text)).get(TABLES))
    if all(rename(identity) == identity for identity in tables):
        return None

    def change(document: CommentedMap) -> None:
        mapping = document[TABLES]
        for position, identity in enumerate(list(mapping)):
            if rename(identity) != identity:
                comment = mapping.ca.items.pop(identity, None)
                mapping.insert(position, rename(identity), mapping.pop(identity))
                if comment is not None:
                    mapping.ca.items[rename(identity)] = comment

    return _rewritten(path, text, change)


def _rewritten(path: Path, text: str, change: Callable[[CommentedMap], None]) -> str:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    try:
        document, indent, offset = load_yaml_guess_indent(text, yaml=yaml)
    except YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML: {exc}") from exc
    yaml.indent(mapping=indent or 2, sequence=(indent or 2) + (offset or 0), offset=offset or 0)
    if document is not None and not isinstance(document, CommentedMap):
        raise ValueError(f"{path}: an annotation file holds a mapping")
    preamble = text if document is None else ""
    document = CommentedMap() if document is None else document
    change(document)
    stream = io.StringIO()
    if document:
        yaml.dump(document, stream)
    return (preamble.rstrip("\n") + "\n" if preamble.strip() else "") + stream.getvalue()


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _empty(value: object) -> bool:
    return value is None or value in ("", [], {})


def _put(item: dict[str, Any], key: str, value: object) -> None:
    shadow = item.setdefault(FROM_DATA, {})
    shadow.setdefault(key, item.get(key))
    if _empty(value):
        item.pop(key, None)
    else:
        item[key] = copy.deepcopy(value)


def _person(value: object) -> object:
    if isinstance(value, str):
        return {"@type": "Person", "name": value}
    if isinstance(value, dict) and "@type" not in value:
        return {"@type": "Person", **value}
    return value


def _creators(value: object) -> object:
    if _empty(value):
        return value
    return [_person(item) for item in value] if isinstance(value, list) else _person(value)


def names(value: object) -> list[str]:
    return [value] if isinstance(value, str) else [str(item) for item in value] if isinstance(value, list) else []


def _key(value: object, fields: Mapping[str, dict[str, Any]]) -> object:
    references = [{"@id": fields[name]["@id"]} for name in names(value) if name in fields]
    return references[0] if isinstance(value, str) and references else references


def columns(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    value = record.get("field")
    fields = [value] if isinstance(value, dict) else value or []
    return {field["name"]: field for field in fields if isinstance(field, dict) and isinstance(field.get("name"), str)}


def _items(data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield data
    yield from (entry for entry in data.get("distribution") or [] if isinstance(entry, dict))
    for record in data.get("recordSet") or []:
        if isinstance(record, dict):
            yield record
            yield from _fields(record)


def _fields(item: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in ("field", "subField"):
        value = item.get(key)
        for field in [value] if isinstance(value, dict) else value or []:
            if isinstance(field, dict):
                yield field
                yield from _fields(field)
