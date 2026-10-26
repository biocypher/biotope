from __future__ import annotations

import ast
import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from biotope.croissant.ids import renamer
from biotope.graph.discovery import discover_packages, discover_roots
from biotope.graph.render import relative_path, render_root
from biotope.graph.revisions import ContractStore
from biotope.graph.sources import read_metadata, write_text_atomic
from biotope.graph.targets import manifest_targets


def _write(path: Path, text: str) -> Path:
    write_text_atomic(path, text)
    Path(importlib.util.cache_from_source(str(path))).unlink(missing_ok=True)
    return path


def _rewrite(path: Path, revisions: dict[str, str], renamed: Callable[[str], str]) -> Path:
    def replace(value: str) -> str:
        return revisions.get(value) or renamed(value)

    text = path.read_text(encoding="utf-8")
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
    return _write(path, "".join(lines))


def follow_ids(sources: Path, manifest: Path, before: dict[str, Any], mapping: dict[str, str]) -> list[Path]:
    renamed = renamer(mapping)
    old = {target.identity: target for target in manifest_targets(before)}
    new = {target.identity: target for target in manifest_targets(read_metadata(manifest))}
    store = ContractStore.for_manifest(manifest)
    written: list[Path] = []
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
            written.append(_rewrite(package.schema, revisions, renamed))
            if revisions and store is not None:
                written += [path for path in [store.record(current.kind, current.definition)] if path is not None]
    return written


def follow_manifest(sources: Path, old: Path, new: Path) -> list[Path]:
    written: list[Path] = []
    for root in discover_roots(sources):
        if root.metadata != old.resolve():
            continue
        written.append(_write(root.path / "__init__.py", render_root(new, root.path)))
        for package in discover_packages(root.path):
            registration = package.path / "__init__.py"
            text = registration.read_text(encoding="utf-8") if registration.is_file() else ""
            before, after = (json.dumps(relative_path(path, package.path), ensure_ascii=False) for path in (old, new))
            if before in text:
                written.append(_write(registration, text.replace(before, after)))
    return written
