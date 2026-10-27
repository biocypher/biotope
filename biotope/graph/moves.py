from __future__ import annotations

import ast
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from biotope.croissant.ids import renamer
from biotope.graph.discovery import discover_packages, discover_roots
from biotope.graph.render import relative_path, render_root
from biotope.graph.revisions import ContractStore
from biotope.graph.sources import write_module
from biotope.graph.targets import Target, manifest_targets


def _rewritten(text: str, revisions: dict[str, str], renamed: Callable[[str], str]) -> str:
    def replace(value: str) -> str:
        return revisions.get(value) or renamed(value)

    tree = ast.parse(text)
    formatted = {id(part) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for part in node.values}
    edits = [
        (node.lineno - 1, node.col_offset, node.end_col_offset or 0, replace(node.value))
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.lineno == node.end_lineno
        and id(node) not in formatted
        and replace(node.value) != node.value
    ]
    lines = text.splitlines(keepends=True)
    for line, start, end, value in sorted(edits, reverse=True):
        encoded = lines[line].encode()
        lines[line] = (encoded[:start] + json.dumps(value, ensure_ascii=False).encode() + encoded[end:]).decode()
    return "".join(lines)


def planned_ids(
    sources: Path, manifest: Path, before: dict[str, Any], after: dict[str, Any], mapping: dict[str, str]
) -> tuple[dict[Path, str], list[Target]]:
    renamed = renamer(mapping)
    old = {target.identity: target for target in manifest_targets(before)}
    new = {target.identity: target for target in manifest_targets(after)}
    schemas: dict[Path, str] = {}
    revised: list[Target] = []
    for root in discover_roots(sources):
        if root.metadata != manifest.resolve():
            continue
        for package in discover_packages(root.path):
            declared = package.declaration
            previous = old.get(declared.identity or "")
            current = new.get(renamed(declared.identity or ""))
            if previous is None or current is None:
                continue
            revisions = {previous.revision: current.revision} if declared.revision == previous.revision else {}
            if current.identity == previous.identity and current.revision == previous.revision:
                continue
            schemas[package.schema] = _rewritten(package.schema.read_text(encoding="utf-8"), revisions, renamed)
            revised += [current] if revisions else []
    return schemas, revised


def write_ids(manifest: Path, schemas: dict[Path, str], revised: list[Target]) -> list[Path]:
    written = [write_module(path, text) for path, text in schemas.items()]
    store = ContractStore.for_manifest(manifest)
    recorded = [store.record(target.kind, target.definition) for target in revised] if store is not None else []
    return written + [path for path in recorded if path is not None]


def package_files(sources: Path, manifest: Path) -> list[Path]:
    roots = [root.path for root in discover_roots(sources) if root.metadata == manifest.resolve()]
    return [path for root in roots for path in root.rglob("*.py")]


def follow_manifest(sources: Path, old: Path, new: Path) -> list[Path]:
    written: list[Path] = []
    for root in discover_roots(sources):
        if root.metadata != old.resolve():
            continue
        written.append(write_module(root.path / "__init__.py", render_root(new, root.path)))
        for package in discover_packages(root.path):
            registration = package.path / "__init__.py"
            text = registration.read_text(encoding="utf-8") if registration.is_file() else ""
            before, after = (json.dumps(relative_path(path, package.path), ensure_ascii=False) for path in (old, new))
            if before in text:
                written.append(write_module(registration, text.replace(before, after)))
    return written
