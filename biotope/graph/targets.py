"""What a manifest describes that needs a source package: every RecordSet, and every file no RecordSet reads."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from pathlib import PurePosixPath
from typing import Any, cast

from biotope.graph.sources import (
    KINDS,
    Kind,
    RecordSetTarget,
    digest,
    file_definition,
    objects,
    record_set_definition,
    record_set_targets,
    resource_kind,
    slug,
    walk_fields,
)


@dataclass(frozen=True)
class Target:
    """One described input that needs a source package, with the preferred name of that package."""

    identity: str
    kind: Kind
    name: str
    entry: dict[str, Any]
    definition: dict[str, Any]

    @cached_property
    def revision(self) -> str:
        return digest(self.definition)

    @property
    def label(self) -> str:
        return KINDS[self.kind].label


def _identities(value: object) -> set[str]:
    """The identities a reference names: an ``@id`` string, an ``{"@id": ...}`` object, or a list of either."""
    entries = cast(list[object], value) if isinstance(value, list) else [value]
    found: set[str] = set()
    for entry in entries:
        if isinstance(entry, dict):
            entry = cast(dict[str, object], entry).get("@id")
        if isinstance(entry, str):
            found.add(entry)
    return found


def _read_files(records: tuple[RecordSetTarget, ...]) -> set[str]:
    """The file resources some RecordSet field reads."""
    found: set[str] = set()
    for record in records:
        for node in walk_fields(record.record, record.identity):
            source: object = node.item.get("source")
            if isinstance(source, dict):
                typed = cast(dict[str, object], source)
                found |= _identities(typed.get("fileObject")) | _identities(typed.get("fileSet"))
    return found


def _preferred_name(resource: dict[str, Any], identity: str) -> str:
    name = resource.get("name")
    if isinstance(name, str) and name.strip():
        return name
    content = resource.get("contentUrl")
    return (PurePosixPath(content).name if isinstance(content, str) else "") or identity


def manifest_targets(data: dict[str, Any]) -> tuple[Target, ...]:
    """Every top-level RecordSet, then every file resource no RecordSet field reads and nothing is ``containedIn``."""
    records = record_set_targets(data)
    targets = [
        Target(item.identity, "recordSet", item.package, item.record, record_set_definition(data, item))
        for item in records
    ]
    distribution = objects(data.get("distribution", []), "/distribution")
    covered = _read_files(records) | {
        container for resource in distribution for container in _identities(resource.get("containedIn"))
    }
    for resource in distribution:
        identity, kind = resource.get("@id"), resource_kind(resource)
        if kind is None or not isinstance(identity, str) or not identity or identity in covered:
            continue
        name = slug(_preferred_name(resource, identity))
        targets.append(Target(identity, kind, name, resource, file_definition(data, resource)))
    return tuple(targets)


def declared_identities(data: dict[str, Any]) -> Iterator[str]:
    """Every identity a package or a field source can name, whether or not it needs a package of its own."""
    yield from (item.identity for item in record_set_targets(data))
    for resource in objects(data.get("distribution", []), "/distribution"):
        identity = resource.get("@id")
        if isinstance(identity, str) and identity:
            yield identity


def unidentified_files(data: dict[str, Any]) -> list[str]:
    """File resources no package can bind to, because they declare no ``@id``."""
    found: list[str] = []
    for index, resource in enumerate(objects(data.get("distribution", []), "/distribution")):
        kind, identity = resource_kind(resource), resource.get("@id")
        if kind is not None and not (isinstance(identity, str) and identity):
            name = resource.get("name") or resource.get("contentUrl") or resource.get("includes")
            described = f" ({name})" if isinstance(name, str) else ""
            found.append(f"the {KINDS[kind].label} at /distribution/{index}{described}")
    return found


def unscoped_fields(target: Target) -> list[str]:
    """Field identities of a RecordSet that are not scoped under their parent's."""
    if target.kind != "recordSet":
        return []
    return [node.identity for node in walk_fields(target.entry, target.identity) if not node.scoped]
