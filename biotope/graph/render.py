"""Render the files of a source package and of a generated root from the templates."""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
from string import Template
from typing import Any, cast

from biotope.graph.sources import (
    KINDS,
    FieldNode,
    Kind,
    attribute_name,
    child_fields,
    python_class_name,
    scalar_type,
)
from biotope.graph.targets import Target


TEMPLATES = Path(__file__).resolve().parents[1] / "templates/source"

# get_type_hints evaluates annotations in the class namespace, where an attribute with one of these names
# would shadow the name the annotation means.
SCHEMA_NAMES = frozenset(
    {"str", "int", "float", "bool", "list", "frozenset", "source_field", "UnknownValue", "ClassVar"}
)

# The names the source templates import or define.
TEMPLATE_NAMES = frozenset(
    {
        "Path",
        "SourceContract",
        "SOURCE",
        "Iterator",
        "RunContext",
        "SourceRecord",
        "annotations",
        "dataclass",
        "ClassVar",
        "source_field",
        "UnknownValue",
        "load",
    }
)

# Biotope's own ruff line length, so that formatting generated code with it changes nothing.
LINE_LENGTH = 120

DOCUMENT_FORMATS = frozenset({"application/pdf", "text/plain", "text/markdown", "text/x-markdown"})
DOCUMENT_SUFFIXES = frozenset({".pdf", ".txt", ".md", ".markdown"})


def _template(name: str) -> Template:
    return Template((TEMPLATES / name).read_text(encoding="utf-8"))


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def relative_path(path: Path, start: Path) -> str:
    return Path(os.path.relpath(path.resolve(), start.resolve())).as_posix()


def render_root(metadata: Path, root: Path) -> str:
    identity = json.dumps({"metadata": relative_path(metadata, root)}, separators=(",", ":"), ensure_ascii=False)
    return _template("root.py.tmpl").substitute(marker=identity, manifest=metadata.resolve().name)


def render_inventory() -> str:
    return _template("inventory.py.tmpl").substitute()


def _class_import(class_name: str) -> tuple[str, str]:
    """How the templates import a record class, aliased when its name would shadow theirs."""
    if class_name in TEMPLATE_NAMES:
        return f"{class_name} as {class_name}Record", f"{class_name}Record"
    return class_name, class_name


def new_class_name(target: Target, package: str) -> str:
    if target.kind != "recordSet":
        return "Facts"
    name = python_class_name(package)
    return name + "Record" if name in TEMPLATE_NAMES else name


def render_package(metadata: Path, directory: Path, name: str, class_name: str) -> str:
    class_import, class_ref = _class_import(class_name)
    return _template("package.py.tmpl").substitute(
        class_import=class_import,
        class_ref=class_ref,
        name=_quoted(name),
        metadata=_quoted(relative_path(metadata, directory)),
    )


def _signature(name: str, parameter: str, returns: str) -> str:
    """A one-parameter ``def`` line, split the way ruff formats it when it exceeds the line length."""
    line = f"def {name}({parameter}) -> {returns}:"
    return line if len(line) <= LINE_LENGTH else f"def {name}(\n    {parameter},\n) -> {returns}:"


def render_loader(kind: Kind, class_name: str) -> str:
    if kind == "recordSet":
        summary = "Yield one record per source row, preserving every described field."
        detail = (
            "Attach Evidence(artifact, version, record_set, location) to each record: the\n"
            'file path, its pinned digest ("sha256:<FileObject sha256>"), the schema\'s\n'
            '__record_set__ and a row locator such as "row 1". Do not filter, impute or\n'
            "deduplicate here; selection belongs to mappings."
        )
    else:
        summary = "Yield the reviewed facts transcribed from this file."
        detail = (
            "Cite the file's pinned digest and each page or section read in the Evidence\n"
            "locations. Record only what the file states; interpretation belongs to mappings."
        )
    class_import, class_ref = _class_import(class_name)
    returns = f"Iterator[SourceRecord[{class_ref}]]"
    return _template("loader.py.tmpl").substitute(
        class_import=class_import,
        read_signature=_signature("_read", "config: None", returns),
        load_signature=_signature("load", "context: RunContext", returns),
        read_summary=summary,
        read_detail="\n    ".join(detail.splitlines()),
    )


def _document_hint(resource: dict[str, Any]) -> str:
    encoding: object = resource.get("encodingFormat")
    values: list[object] = cast(list[object], encoding) if isinstance(encoding, list) else [encoding]
    formats = {value for value in values if isinstance(value, str)}
    content = resource.get("contentUrl")
    suffix = PurePosixPath(content).suffix.lower() if isinstance(content, str) else ""
    if formats & DOCUMENT_FORMATS or suffix in DOCUMENT_SUFFIXES:
        return "Author reviewed facts as fields; loader.py returns them with page or section locations."
    return (
        "Describe this file with a RecordSet in the manifest, author reviewed facts here, "
        "or exclude it in graph/sources/__init__.py."
    )


def _render_file(target: Target, class_name: str) -> str:
    return _template("file.py.tmpl").substitute(
        hint=_document_hint(target.entry),
        class_name=class_name,
        attribute=KINDS[target.kind].attribute,
        identity=_quoted(target.identity),
        record_set=_quoted(target.identity + "/facts"),
        digest=_quoted(target.revision),
    )


def _source_argument(attribute: str, node: FieldNode) -> str | None:
    """The ``source_field`` argument binding an attribute to a scoped field, or None when the bare attribute does.

    The argument is the field's ``@id`` suffix, or its whole ``@id`` when the suffix is empty or would
    itself read as scoped.
    """
    suffix = node.identity[len(node.scope) + 1 :]
    if suffix == attribute:
        return None
    if not suffix or suffix.startswith(node.scope + "/"):
        return _quoted(node.identity)
    return _quoted(suffix)


class _RecordClasses:
    """The classes of one RecordSet schema, each nested field record before the class that holds it."""

    def __init__(self, revision: str, class_name: str) -> None:
        self.revision = revision
        self.names = {"UnknownValue", "ClassVar", "dataclass", "annotations", "source_field", class_name}
        self.blocks: list[str] = []
        self.binds = False
        self.opaque = False

    def add(self, nodes: list[FieldNode], scope: str, name: str, *, nested: bool = False) -> str:
        used = {"__record_set__", "__source_digest__", "__missing_values__", "__field_refs__", *SCHEMA_NAMES}
        lines = [line for node in nodes for line in self._field(node, name, used)]
        header = [
            "@dataclass(frozen=True, kw_only=True)",
            f"class {name}:",
            f"    __record_set__: ClassVar[str] = {_quoted(scope)}",
        ]
        if not nested:
            header += [
                f"    __source_digest__: ClassVar[str] = {_quoted(self.revision)}",
                '    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})',
            ]
        self.blocks.append("\n".join([*header, *([""] if lines else []), *lines]))
        return name

    def _field(self, node: FieldNode, owner: str, used: set[str]) -> list[str]:
        attribute = attribute_name(node.item.get("name", node.item.get("@id", "unnamed")), used)
        children = node.children()
        if children:
            nested = attribute_name(f"{owner}_{attribute}", self.names, class_name=True)
            annotation = self.add(children, node.identity, nested, nested=True)
        else:
            annotation = scalar_type(node.item.get("dataType"))
        shape = node.item.get("arrayShape", node.item.get("cr:arrayShape"))
        if shape is not None:
            annotation = "UnknownValue"
        self.opaque |= annotation == "UnknownValue"
        if shape is None and node.item.get("repeated", node.item.get("isArray", node.item.get("cr:isArray", False))):
            annotation = f"list[{annotation} | None]"
        if node.nullable:
            annotation += " | None"
        default = ", default=None" if node.nullable else ""
        if not node.scoped:
            self.binds = True
            return [
                f"    # Unscoped field @id {_quoted(node.identity)}: rescope it under {_quoted(node.scope + '/')}.",
                f"    {attribute}: {annotation} = source_field(None{default})",
            ]
        argument = _source_argument(attribute, node)
        if argument is None:
            return [f"    {attribute}: {annotation}" + (" = None" if node.nullable else "")]
        self.binds = True
        return [f"    {attribute}: {annotation} = source_field({argument}{default})"]


def _render_record_set(target: Target, class_name: str) -> str:
    classes = _RecordClasses(target.revision, class_name)
    classes.add(child_fields(target.entry, target.identity, target.identity), target.identity, class_name)
    graph_names = [name for name, used in (("UnknownValue", classes.opaque), ("source_field", classes.binds)) if used]
    imports = ["from dataclasses import dataclass", "from typing import ClassVar"]
    if graph_names:
        imports += ["", f"from biotope.graph import {', '.join(graph_names)}"]
    text = _template("record_set.py.tmpl").substitute(
        imports="\n".join(imports),
        classes="\n\n\n".join(classes.blocks),
    )
    return text.rstrip() + "\n"


def render_schema(target: Target, class_name: str) -> str:
    """Render the initial, project-owned schema; for a RecordSet, types, nesting and nullability follow the manifest."""
    if target.kind == "recordSet":
        return _render_record_set(target, class_name)
    return _render_file(target, class_name)
