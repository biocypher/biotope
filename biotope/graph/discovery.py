"""Find source packages: statically by parsing their schemas, and at import time by collecting registrations.

Static discovery reads ``schema.py`` as syntax and never imports it, so it still works when project
code does not. A package belongs to the identity its schema declares, whatever its directory is called.
"""

from __future__ import annotations

import ast
import importlib
import keyword
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, cast

from biotope.graph.contracts import SourceContract
from biotope.graph.sources import (
    GENERATED_HEADER,
    KINDS,
    LEGACY_HEADER,
    MANIFEST_MARKER,
    PLACEHOLDER_MARKER,
    RECORD_SET_MARKER,
    Kind,
    marker,
)


def is_identifier(name: str) -> bool:
    return name.isidentifier() and not keyword.iskeyword(name)


def is_package_name(name: str) -> bool:
    """Whether discovery sees a directory of this name as a package: importable, and not dunder."""
    return is_identifier(name) and not name.startswith("__")


def _visible_directories(directory: Path) -> Iterator[Path]:
    if not directory.is_dir():
        return
    for child in sorted(directory.iterdir(), key=lambda path: path.name):
        if not child.name.startswith((".", "__")) and not child.is_symlink() and child.is_dir():
            yield child


def package_directories(directory: Path) -> Iterator[Path]:
    """The directories under a root that can be imported as packages, in name order."""
    return (child for child in _visible_directories(directory) if is_identifier(child.name))


def unimportable_packages(root: Path) -> list[Path]:
    """Directories with a ``schema.py`` whose names cannot be imported, so collection never sees them."""
    return [
        child
        for child in _visible_directories(root)
        if not is_identifier(child.name) and (child / "schema.py").is_file()
    ]


def root_manifest(text: str) -> str | None:
    """Return the manifest a generated root file names, for the current and the 0.9 form."""
    if not text.startswith((GENERATED_HEADER, LEGACY_HEADER)):
        return None
    return marker(text, MANIFEST_MARKER, "metadata")


def is_generated(text: str) -> bool:
    return text.startswith(GENERATED_HEADER)


def generated_root(directory: Path) -> str | None:
    """Return the manifest a directory's generated ``__init__.py`` names, or None when it is not a root."""
    init = directory / "__init__.py"
    if not init.is_file() or init.is_symlink():
        return None
    return root_manifest(init.read_text(encoding="utf-8", errors="replace"))


def is_placeholder(loader: Path) -> bool:
    """Only an exact first line marks a loader as an unimplemented placeholder."""
    try:
        with loader.open(encoding="utf-8") as stream:
            return stream.readline().rstrip("\r\n") == PLACEHOLDER_MARKER
    except OSError:
        return False


def _imported_path(package: str) -> Path:
    module = sys.modules.get(package)
    locations = cast("list[str] | None", getattr(module, "__path__", None)) if module is not None else None
    if not locations:
        raise ValueError(f"{package!r} is not an imported package")
    return Path(next(iter(locations)))


def collect_contracts(package: str) -> tuple[SourceContract, ...]:
    """Collect ``SOURCE`` from every package with a ``schema.py`` under one generated root."""
    contracts: list[SourceContract] = []
    for child in package_directories(_imported_path(package)):
        if not (child / "schema.py").is_file():
            continue
        source = getattr(importlib.import_module(f"{package}.{child.name}"), "SOURCE", None)
        if not isinstance(source, SourceContract):
            raise ValueError(
                f"{child}: a source package registers SOURCE = SourceContract(...) in __init__.py; "
                "run biotope source generate to complete it"
            )
        contracts.append(source)
    return tuple(contracts)


def collect_inventory(module: str) -> tuple[SourceContract, ...]:
    """Collect ``CONTRACTS`` from every generated root beside the calling module, in name order."""
    parent = module.rpartition(".")[0]
    if not parent:
        raise ValueError(f"{module!r} must be a module inside the sources package")
    contracts: list[SourceContract] = []
    for child in package_directories(_imported_path(parent)):
        if generated_root(child) is None:
            continue
        found: object = getattr(importlib.import_module(f"{parent}.{child.name}"), "CONTRACTS", None)
        items = cast(tuple[object, ...], found) if isinstance(found, tuple) else None
        if items is None or any(not isinstance(item, SourceContract) for item in items):
            raise ValueError(
                f"{child / '__init__.py'}: a generated root defines CONTRACTS as a tuple of SourceContract"
            )
        contracts.extend(cast(tuple[SourceContract, ...], items))
    return tuple(contracts)


@dataclass(frozen=True)
class Declaration:
    """What one ``schema.py`` declares, read without importing it."""

    identity: str | None
    kind: Kind | None
    class_name: str | None
    revision: str | None
    field_refs: bool = False
    problem: str = ""
    other_identities: tuple[str, ...] = ()

    @classmethod
    def unreadable(cls, problem: str, identity: str | None = None) -> Declaration:
        return cls(identity, None, None, None, problem=problem)


class _Declarer(NamedTuple):
    kind: Kind
    class_name: str
    revision: str | None
    field_refs: bool


def _assignment(node: ast.stmt) -> tuple[str | None, ast.expr | None]:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id, node.value
    return None, None


def _string(value: ast.expr | None, constants: dict[str, str]) -> str | None:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.Name):
        return constants.get(value.id)
    return None


def _declarers(tree: ast.Module) -> dict[str, list[_Declarer]]:
    """Every identity a class in the module declares, with the classes declaring it."""
    constants: dict[str, str] = {}
    for node in tree.body:
        name, value = _assignment(node)
        found = _string(value, {})
        if name is not None and found is not None:
            constants[name] = found
    attributes = [spec.attribute for spec in KINDS.values()]
    declared: dict[str, list[_Declarer]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        values: dict[str, str | None] = {}
        field_refs = False
        for item in node.body:
            name, value = _assignment(item)
            if name in (*attributes, "__source_digest__"):
                values[name] = _string(value, constants)
                if values[name] is None:
                    raise ValueError(f"{node.name}.{name} is not a string literal or constant")
            field_refs |= name == "__field_refs__"
        for kind, spec in KINDS.items():
            identity = values.get(spec.attribute)
            if identity:
                declarer = _Declarer(kind, node.name, values.get("__source_digest__"), field_refs)
                declared.setdefault(identity, []).append(declarer)
                break
    return declared


def read_declaration(path: Path) -> Declaration:
    """Read a schema's declared identity, kind, class and reviewed revision.

    Classes scoped under another declared identity (nested field records, document facts) do not
    compete for the package.
    """
    try:
        text = path.read_text(encoding="utf-8")
        declared = _declarers(ast.parse(text, filename=str(path)))
    except UnicodeDecodeError as exc:
        return Declaration.unreadable(f"is not UTF-8 text: {exc.reason}")
    except SyntaxError as exc:
        return Declaration.unreadable(f"cannot be parsed: {exc.msg} (line {exc.lineno})")
    except ValueError as exc:
        return Declaration.unreadable(str(exc))
    legacy = marker(text, RECORD_SET_MARKER, "id")
    if not declared and legacy:
        return Declaration(legacy, "recordSet", None, None)
    top = sorted(i for i in declared if not any(i.startswith(other + "/") for other in declared if other != i))
    candidates = top
    if len(top) > 1:
        with_revision = [i for i in top if any(declarer.revision for declarer in declared[i])]
        if len(with_revision) == 1:
            top = with_revision
        elif legacy in top:
            top = [legacy]
    if not top:
        return Declaration.unreadable("declares no __record_set__, __file_object__ or __file_set__")
    if len(top) > 1:
        return Declaration.unreadable("declares several source identities: " + ", ".join(repr(i) for i in top))
    [identity] = top
    declarers = declared[identity]
    if len(declarers) > 1:
        names = ", ".join(declarer.class_name for declarer in declarers)
        return Declaration.unreadable(f"several classes declare {identity!r}: {names}", identity)
    [declarer] = declarers
    others = tuple(other for other in candidates if other != identity)
    return Declaration(identity, declarer.kind, declarer.class_name, declarer.revision, declarer.field_refs, "", others)


@dataclass(frozen=True)
class Package:
    """One directory with a ``schema.py`` inside a manifest root."""

    name: str
    path: Path
    declaration: Declaration

    @property
    def schema(self) -> Path:
        return self.path / "schema.py"


def discover_packages(root: Path) -> tuple[Package, ...]:
    """Every package directory with a ``schema.py`` under one root, with its declaration."""
    return tuple(
        Package(child.name, child, read_declaration(child / "schema.py"))
        for child in package_directories(root)
        if (child / "schema.py").is_file()
    )


@dataclass(frozen=True)
class Root:
    """One generated manifest root under the sources package."""

    name: str
    path: Path
    metadata: Path


def discover_roots(sources: Path) -> tuple[Root, ...]:
    """Every generated root under the sources package, with the manifest its marker names."""
    roots: list[Root] = []
    for child in package_directories(sources):
        relative = generated_root(child)
        if relative is not None:
            roots.append(Root(child.name, child, (child / relative).resolve()))
    return tuple(roots)
