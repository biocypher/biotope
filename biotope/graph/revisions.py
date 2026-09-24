"""Contract history: a content-addressed store of reviewed source revisions, and the drift between them.

Each ``.biotope/contracts/<digest>.json`` holds the exact digest preimage and is trusted only while it
hashes to its name, so drift can itemize any change to what was reviewed, ``@context`` and ordering included.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from biotope.graph.sources import FieldNode, Kind, digest, walk_fields, write_text_atomic


STORE = Path(".biotope/contracts")
DIFF_VALUE_LIMIT = 80
DRIFT_LINE_LIMIT = 20


def project_root(path: Path) -> Path | None:
    """The nearest ancestor of a path that holds ``.biotope/``, if it is inside a Biotope project."""
    return next((parent for parent in path.resolve().parents if (parent / ".biotope").is_dir()), None)


def short_revision(revision: str | None) -> str:
    return (revision or "none")[:12]


class ContractStore:
    """Append-only snapshots of every reviewed source revision in one project."""

    def __init__(self, project: Path) -> None:
        self.project = project
        self.directory = project / STORE

    @classmethod
    def for_manifest(cls, metadata: Path) -> ContractStore | None:
        project = project_root(metadata)
        return cls(project) if project is not None else None

    def path(self, revision: str) -> Path:
        return self.directory / f"{revision}.json"

    def get(self, revision: str) -> dict[str, Any] | None:
        """Return the recorded definition of a revision, or None if absent or corrupt."""
        path = self.path(revision)
        if not path.is_file() or path.is_symlink():
            return None
        try:
            entry: object = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(entry, dict):
            return None
        found = cast(dict[str, object], entry).get("definition")
        if not isinstance(found, dict):
            return None
        definition = cast(dict[str, Any], found)
        return definition if digest(definition) == revision else None

    def record(self, kind: Kind, definition: dict[str, Any]) -> Path | None:
        """Record one definition under its revision if it is not recorded yet; return the new file."""
        revision = digest(definition)
        if self.get(revision) is not None:
            return None
        path = self.path(revision)
        if path.is_symlink():
            raise ValueError(f"Refusing to write through symlink {path}")
        entry = {"digest": revision, "kind": kind, "definition": definition}
        write_text_atomic(path, json.dumps(entry, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        return path


def _escape(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def _value(value: object) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return text if len(text) <= DIFF_VALUE_LIMIT else text[: DIFF_VALUE_LIMIT - 1] + "…"


@dataclass(frozen=True)
class Change:
    """One JSON-pointer difference between two contract definitions."""

    operation: Literal["added", "removed", "changed"]
    pointer: str
    old: object = None
    new: object = None

    def render(self) -> str:
        if self.operation == "added":
            return f"added {self.pointer or '/'}: {_value(self.new)}"
        if self.operation == "removed":
            return f"removed {self.pointer or '/'}: {_value(self.old)}"
        return f"changed {self.pointer or '/'}: {_value(self.old)} -> {_value(self.new)}"

    def to_json(self) -> dict[str, object]:
        return {"operation": self.operation, "pointer": self.pointer, "old": self.old, "new": self.new}


def pointer_diff(old: object, new: object, pointer: str = "") -> list[Change]:
    """Every difference between two JSON values, list positions included."""
    if isinstance(old, dict) and isinstance(new, dict):
        before, after = cast(dict[str, object], old), cast(dict[str, object], new)
        changes: list[Change] = []
        for key in sorted(set(before) | set(after)):
            path = f"{pointer}/{_escape(key)}"
            if key not in after:
                changes.append(Change("removed", path, old=before[key]))
            elif key not in before:
                changes.append(Change("added", path, new=after[key]))
            else:
                changes.extend(pointer_diff(before[key], after[key], path))
        return changes
    if isinstance(old, list) and isinstance(new, list):
        before_items, after_items = cast(list[object], old), cast(list[object], new)
        changes = []
        for index in range(max(len(before_items), len(after_items))):
            path = f"{pointer}/{index}"
            if index >= len(after_items):
                changes.append(Change("removed", path, old=before_items[index]))
            elif index >= len(before_items):
                changes.append(Change("added", path, new=after_items[index]))
            else:
                changes.extend(pointer_diff(before_items[index], after_items[index], path))
        return changes
    before_value: object = cast(object, old)
    after_value: object = new
    if type(before_value) is not type(after_value) or before_value != after_value:
        return [Change("changed", pointer, before_value, after_value)]
    return []


FIELD_PROPERTIES = ("dataType", "extract", "columnIndex", "nullable")


def _property(node: FieldNode, name: str) -> object:
    if name == "extract":
        source: object = node.item.get("source")
        return cast(dict[str, object], source).get("extract") if isinstance(source, dict) else None
    if name == "columnIndex":
        return node.item.get("biotope:columnIndex")
    if name == "nullable":
        return node.nullable
    return node.item.get(name)


def _fields(definition: dict[str, Any]) -> dict[str, FieldNode] | None:
    """A RecordSet definition's fields by identity, or None for a file definition."""
    records = definition.get("recordSet")
    if not isinstance(records, list) or len(cast(list[object], records)) != 1:
        return None
    record = cast(list[object], records)[0]
    if not isinstance(record, dict):
        return None
    typed = cast(dict[str, Any], record)
    return {node.identity: node for node in walk_fields(typed, str(typed.get("@id", "/recordSet/0")))}


def field_summary(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Field-level changes matched by ``@id``: added, removed and changed properties."""
    old_fields, new_fields = _fields(old), _fields(new)
    if old_fields is None or new_fields is None:
        return []
    lines = [f"field added: {identity}" for identity in new_fields if identity not in old_fields]
    lines += [f"field removed: {identity}" for identity in old_fields if identity not in new_fields]
    for identity, node in new_fields.items():
        previous = old_fields.get(identity)
        if previous is None:
            continue
        for name in FIELD_PROPERTIES:
            before_value, after_value = _property(previous, name), _property(node, name)
            if before_value != after_value:
                lines.append(f"field {identity}: {name} {_value(before_value)} -> {_value(after_value)}")
    shared = [identity for identity in old_fields if identity in new_fields]
    if shared != [identity for identity in new_fields if identity in old_fields]:
        lines.append("field order changed")
    return lines


@dataclass(frozen=True)
class Drift:
    """Why a package's acknowledged revision differs from the manifest's current one."""

    summary: tuple[str, ...]
    changes: tuple[Change, ...]
    available: bool

    def lines(self, limit: int | None = None) -> list[str]:
        if not self.available:
            return list(self.summary)
        rendered = [*self.summary, *(change.render() for change in self.changes)]
        if limit is not None and len(rendered) > limit:
            return [*rendered[:limit], f"(+{len(rendered) - limit} more differences; see --json)"]
        return rendered


def explain_drift(store: ContractStore | None, declared: str | None, current: dict[str, Any]) -> Drift:
    """Explain a revision change from the recorded definition, or say why it cannot be itemized."""
    previous = store.get(declared) if store is not None and declared else None
    if previous is None:
        if store is None:
            reason = "this manifest is not managed by a Biotope project, so no contract history is kept"
        elif declared and store.path(declared).exists():
            reason = f"the recorded entry of revision {short_revision(declared)} no longer matches its digest"
        else:
            reason = f"the acknowledged revision {short_revision(declared)} is not recorded in {STORE}"
        return Drift((f"{reason}; the change cannot be itemized",), (), False)
    changes = tuple(pointer_diff(previous, current))
    summary = field_summary(previous, current)
    if changes and all(change.pointer.startswith("/@context") for change in changes):
        summary.insert(0, "only @context changed; every contract of this manifest drifts with it")
    return Drift(tuple(summary), changes, True)


def describe_contract(definition: dict[str, Any]) -> list[str]:
    """A compact view of a current contract, shown when its history is unavailable."""
    fields = _fields(definition)
    if fields is not None:
        return [
            f"{identity}: {node.item.get('dataType', 'no dataType')}" + ("" if node.nullable else ", not nullable")
            for identity, node in fields.items()
        ]
    resource = definition.get("distribution")
    if isinstance(resource, dict):
        typed = cast(dict[str, Any], resource)
        return [f"{key}: {_value(typed[key])}" for key in ("contentUrl", "encodingFormat", "sha256") if key in typed]
    return []
