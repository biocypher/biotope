"""Reconcile one manifest with its root: plan what generation would write, then write it.

Generation only creates missing files: it never rewrites a schema, a registration or a loader, and it
writes nothing when it finds a conflict.
"""

from __future__ import annotations

import secrets
import shutil
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from biotope.croissant.ids import MOVED_FROM, moved_from
from biotope.graph.discovery import (
    Package,
    discover_packages,
    discover_roots,
    is_generated,
    is_package_name,
    read_declaration,
    root_manifest,
    unimportable_packages,
)
from biotope.graph.render import (
    new_class_name,
    render_inventory,
    render_loader,
    render_package,
    render_root,
    render_schema,
)
from biotope.graph.revisions import ContractStore, Drift, explain_drift, project_root
from biotope.graph.sources import (
    KINDS,
    RESERVED_NAMES,
    Kind,
    digest,
    objects,
    refresh_description,
    slug,
    walk_fields,
    write_module,
)
from biotope.graph.targets import Target, declared_identities, manifest_targets, unidentified_files
from biotope.metadata import dataset_id


SOURCES_PACKAGE_NAMES = frozenset({"inventory", "INVENTORY", "SOURCES", "EXCLUDED_SOURCES"})
ROOT_MODULE_NAMES = frozenset({"CONTRACTS", "collect_contracts"})

State = Literal["created", "completed", "current", "drift", "orphaned", "conflict"]


@dataclass(frozen=True)
class PackageStatus:
    """One package's or generated file's agreement with the manifest."""

    package: str
    path: Path
    state: State
    identity: str | None = None
    kind: Kind | None = None
    detail: str = ""
    acknowledged: str | None = None
    revision: str | None = None
    drift: Drift | None = None


def _conflict(path: Path, detail: str, package: str = "", identity: str | None = None) -> PackageStatus:
    return PackageStatus(package, path, "conflict", identity, detail=detail)


@dataclass(frozen=True)
class SourcePlan:
    """What reconciling one manifest would write, and why."""

    metadata: Path
    sources: Path
    root: Path
    store: ContractStore | None
    targets: tuple[Target, ...]
    packages: tuple[Package, ...] = ()
    statuses: tuple[PackageStatus, ...] = ()
    new_packages: dict[Path, dict[str, str]] = field(default_factory=dict[Path, dict[str, str]])
    new_files: dict[Path, str] = field(default_factory=dict[Path, str])
    generated_files: dict[Path, str] = field(default_factory=dict[Path, str])

    @property
    def conflicts(self) -> list[PackageStatus]:
        return [status for status in self.statuses if status.state == "conflict"]

    @property
    def changes(self) -> bool:
        return bool(self.new_packages or self.new_files or self.generated_files)


def root_directory(metadata: Path, output: Path, package: str | None = None) -> Path:
    """Resolve and validate the manifest root beneath a sources package."""
    if output.suffix == ".py" or output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ValueError(f"{output} is not a directory; --out is the sources package, e.g. graph/sources")
    held = [root.path for root in discover_roots(output) if root.metadata == metadata.resolve()]
    if package is None and len(held) == 1:
        return held[0]
    name = package or slug(metadata.stem)
    if not is_package_name(name) or name in RESERVED_NAMES or name in SOURCES_PACKAGE_NAMES:
        raise ValueError(f"{name!r} is not a usable root package name; pass --package <name>")
    return output / name


def _claim(base: str, identity: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    for width in range(8, len(digest("")) + 1, 8):
        candidate = f"{base}_{digest(identity)[:width]}"
        if candidate not in taken:
            return candidate
    raise ValueError(f"Cannot name a package for {identity!r}; remove a colliding directory")


def _assign_names(
    targets: tuple[Target, ...], packages: dict[str, str], occupied: set[str], reusable: set[str]
) -> dict[str, str]:
    """Name every target without a package in ``packages``, deterministically given what exists.

    RecordSets keep their 0.9 names, whose collisions count RecordSets only; file resources then
    avoid every taken name. A schema-less directory in ``reusable`` is completed by the target it
    would be named for.
    """
    names: dict[str, str] = {}
    blocked = occupied - reusable
    records = [target for target in targets if target.kind == "recordSet"]
    for target in records:
        if target.identity not in packages:
            names[target.identity] = _claim(target.name, target.identity, blocked | set(names.values()))
    files = [target for target in targets if target.kind != "recordSet" and target.identity not in packages]
    shared = {name for name, count in Counter(target.name for target in files).items() if count > 1}
    taken = blocked | set(RESERVED_NAMES) | {target.name for target in records} | set(names.values()) | shared
    for target in sorted(files, key=lambda item: item.identity):
        names[target.identity] = _claim(target.name, target.identity, taken)
        taken.add(names[target.identity])
    return names


def _root_conflicts(metadata: Path, sources: Path, root: Path) -> list[PackageStatus]:
    """Conflicts over the root itself; its packages then belong to another manifest or layout."""
    manifest = metadata.resolve()
    init = root / "__init__.py"
    found: list[PackageStatus] = []
    if root.is_symlink():
        found.append(_conflict(root, "the root is a symlink; biotope does not write through symlinks"))
    elif init.is_symlink():
        found.append(_conflict(init, "the root inventory is a symlink; biotope does not write through symlinks"))
    elif init.is_file():
        owner = root_manifest(init.read_text(encoding="utf-8", errors="replace"))
        if owner is None:
            found.append(
                _conflict(init, "authored code occupies the generated root inventory; move it or pass --package")
            )
        elif (root / owner).resolve() != manifest:
            found.append(
                _conflict(init, f"root {root.name!r} belongs to {owner}; pass --package to choose another root")
            )
    if (root / "schema.py").is_file():
        found.append(
            _conflict(root / "schema.py", "single-module layout; move it aside so each source gets its own package")
        )
    for other in discover_roots(sources):
        if other.path != root and other.metadata == manifest:
            found.append(_conflict(other.path, f"this manifest is already generated into root {other.name!r}"))
    return found


def _manifest_conflicts(metadata: Path, data: dict[str, Any]) -> tuple[list[PackageStatus], set[str]]:
    """Identities several entries share, and files without one, with the shared identities to withhold."""
    counts = Counter(declared_identities(data))
    shared = {identity for identity, count in counts.items() if count > 1}
    found = [
        _conflict(
            metadata, f"{counts[identity]} entries in {metadata.name} share the @id {identity!r}; give each its own"
        )
        for identity in sorted(shared)
    ]
    found += [
        _conflict(metadata, f"{label} in {metadata.name} has no @id; give it a stable @id so a package can bind to it")
        for label in unidentified_files(data)
    ]
    return found, shared


def _generated_files(metadata: Path, sources: Path, root: Path) -> tuple[dict[Path, str], list[PackageStatus]]:
    """The root's ``__init__.py`` and the sources' ``inventory.py`` that are missing or out of date."""
    files: dict[Path, str] = {}
    conflicts: list[PackageStatus] = []
    init, expected = root / "__init__.py", render_root(metadata, root)
    if not init.exists() or _stale(init.read_text(encoding="utf-8"), expected):
        files[init] = expected
    inventory, expected = sources / "inventory.py", render_inventory()
    if inventory.is_symlink():
        conflicts.append(_conflict(inventory, "inventory.py is a symlink; biotope does not write through symlinks"))
    elif not inventory.exists():
        files[inventory] = expected
    elif not is_generated(text := inventory.read_text(encoding="utf-8")):
        conflicts.append(_conflict(inventory, "authored code occupies the generated inventory.py; move it aside"))
    elif _stale(text, expected):
        files[inventory] = expected
    return files, conflicts


def _stale(text: str, expected: str) -> bool:
    return not is_generated(text) or " ".join(text.split()) != " ".join(expected.split())


@dataclass(frozen=True)
class _Ownership:
    """Which package owns each identity, and which identities no package may be proposed for."""

    owned: dict[str, Package]
    contested: frozenset[str]
    unreadable: bool
    conflicts: tuple[PackageStatus, ...]


def _ownership(root: Path, packages: tuple[Package, ...], live: set[str], manifest: str) -> _Ownership:
    conflicts: list[PackageStatus] = []
    contested: set[str] = set()
    unreadable = False
    claims: dict[str, list[Package]] = {}
    for package in packages:
        declaration = package.declaration
        if declaration.problem:
            conflicts.append(_conflict(package.schema, f"the schema {declaration.problem}", package.name))
            unreadable = True
        elif declaration.identity is not None:
            claims.setdefault(declaration.identity, []).append(package)
            for other in declaration.other_identities:
                if other in live:
                    detail = (
                        f"the schema declares {declaration.identity!r} and also {other!r}, another source of "
                        f"{manifest}; keep one source per schema"
                    )
                    conflicts.append(_conflict(package.schema, detail, package.name, other))
                    contested.add(other)
    for directory in unimportable_packages(root):
        declaration = read_declaration(directory / "schema.py")
        detail = (
            f"{directory.name!r} is not a Python identifier, so its package cannot be imported; rename the directory"
        )
        conflicts.append(_conflict(directory / "schema.py", detail, directory.name, declaration.identity))
        if declaration.identity is None:
            unreadable = True
        else:
            contested.add(declaration.identity)
    for identity, claimed in claims.items():
        if len(claimed) > 1:
            contested.add(identity)
            for package in claimed:
                others = ", ".join(other.name for other in claimed if other is not package)
                conflicts.append(
                    _conflict(package.schema, f"{identity!r} is also declared by {others}", package.name, identity)
                )
    owned = {identity: claimed[0] for identity, claimed in claims.items() if len(claimed) == 1}
    return _Ownership(owned, frozenset(contested), unreadable, tuple(conflicts))


def _occupied(root: Path) -> tuple[set[str], set[str]]:
    """Names a new package may not take, and the schema-less directories a new package may complete."""
    children = list(root.iterdir()) if root.is_dir() else []
    occupied = {child.name for child in children} | {child.stem for child in children if child.suffix == ".py"}
    reusable = {
        child.name
        for child in children
        if child.is_dir() and not child.is_symlink() and not (child / "schema.py").exists()
    }
    return occupied | ROOT_MODULE_NAMES, reusable


def _package_files(metadata: Path, root: Path, directory: Path, target: Target, class_name: str) -> dict[str, str]:
    one_file = target.kind == "fileObject" or (
        target.kind == "recordSet"
        and not any(
            isinstance(source := node.item.get("source"), dict) and "fileSet" in source
            for node in walk_fields(target.entry, target.identity)
        )
    )
    return {
        "__init__.py": render_package(metadata, directory, f"{root.name}/{directory.name}", class_name),
        "loader.py": render_loader(target.kind, class_name, one_file=one_file),
    }


def _missing(directory: Path, files: dict[str, str]) -> dict[Path, str]:
    return {directory / name: text for name, text in files.items() if not (directory / name).exists()}


def _created(paths: dict[Path, str]) -> str:
    return "created " + ", ".join(path.name for path in paths)


def _reconcile_existing(plan: SourcePlan, target: Target, package: Package) -> tuple[PackageStatus, dict[Path, str]]:
    declaration = package.declaration
    if declaration.kind != target.kind:
        declared = KINDS[declaration.kind].label if declaration.kind else "no kind"
        detail = f"declares {declared} {target.identity!r}, but the manifest describes a {target.label}"
        return _conflict(package.schema, detail, package.name, target.identity), {}
    missing: dict[Path, str] = {}
    if not all((package.path / name).exists() for name in ("__init__.py", "loader.py")):
        if declaration.class_name is None:
            detail = "cannot complete the package: no class declares its identity"
            return _conflict(package.schema, detail, package.name, target.identity), {}
        missing = _missing(
            package.path, _package_files(plan.metadata, plan.root, package.path, target, declaration.class_name)
        )
    drifted = declaration.revision != target.revision
    status = PackageStatus(
        package.name,
        package.path,
        "completed" if missing else "drift" if drifted else "current",
        target.identity,
        target.kind,
        _created(missing) if missing else "",
        declaration.revision,
        target.revision,
        explain_drift(plan.store, declaration.revision, target.definition) if drifted else None,
    )
    return status, missing


def _scaffold(plan: SourcePlan, target: Target, directory: Path) -> tuple[PackageStatus, dict[str, str]]:
    """A new package's files, or the files completing a schema-less directory of the same name."""
    class_name = new_class_name(target, directory.name)
    files = {
        "schema.py": render_schema(target, class_name),
        **_package_files(plan.metadata, plan.root, directory, target, class_name),
    }
    if not directory.is_dir():
        return PackageStatus(
            directory.name, directory, "created", target.identity, target.kind, revision=target.revision
        ), files
    missing = _missing(directory, files)
    detail = "the directory had no schema; " + _created(missing)
    status = PackageStatus(
        directory.name, directory, "completed", target.identity, target.kind, detail, revision=target.revision
    )
    return status, {path.name: text for path, text in missing.items()}


def _orphans(plan: SourcePlan, data: dict[str, Any], owned: dict[str, Package]) -> list[PackageStatus]:
    live = {target.identity for target in plan.targets}
    found: list[PackageStatus] = []
    for identity, package in sorted(owned.items(), key=lambda entry: entry[1].name):
        if identity in live:
            continue
        gone = f"{identity!r} is no longer described by {plan.metadata.name}"
        detail = _moved(plan, data, identity, gone, owned) or f"{gone}; delete the directory to remove it"
        declaration = package.declaration
        found.append(
            PackageStatus(
                package.name,
                package.path,
                "orphaned",
                identity,
                declaration.kind,
                detail,
                declaration.revision,
            )
        )
    return found


def _relocated(plan: SourcePlan, data: dict[str, Any], status: PackageStatus) -> PackageStatus:
    origin = data.get(MOVED_FROM)
    project = project_root(plan.metadata)
    if not isinstance(origin, str) or project is None or status.state not in ("current", "drift"):
        return status
    now = dataset_id(plan.metadata.resolve(), project)
    detail = (
        f"{status.identity!r} keeps its ID, but its file moved outside biotope from {origin!r} to {now!r}. "
        "Move the file back, rebake and use biotope mv"
    )
    return replace(status, state="orphaned", detail=detail)


def _moved(plan: SourcePlan, data: dict[str, Any], identity: str, gone: str, owned: dict[str, Package]) -> str:
    moves = {
        old: entry["@id"]
        for entry in objects(data.get("distribution", []), "/distribution")
        if isinstance(entry.get("@id"), str)
        for old in moved_from(entry)
    }
    old = identity.split("#", 1)[0]
    if old not in moves:
        return ""
    new = moves[old]
    now = [target.identity for target in plan.targets if target.identity.split("#", 1)[0] == new]
    described = ", ".join(repr(item) for item in now) or repr(new)
    moved = f"{gone}: its file {old!r} moved outside biotope to {new!r}, now described as {described}."
    project = project_root(plan.metadata)
    generated = " and ".join(
        owned[item].path.resolve().relative_to(project).as_posix() if project else str(owned[item].path)
        for item in now
        if item in owned
    )
    if not generated:
        return (
            f"{moved} Declare the new ID in this package and set the revision graph check names, or move the file "
            "back, rebake and use biotope mv"
        )
    return (
        f"{moved} Delete {generated}, then declare the new ID in this package and set the revision graph check "
        f"names; or move the file back, rebake, use biotope mv and delete {generated}"
    )


def plan_sources(metadata: Path, output: Path, package: str | None = None) -> SourcePlan:
    """Reconcile one manifest with its root without writing anything."""
    root = root_directory(metadata, output, package)
    data = refresh_description(metadata)
    packages = discover_packages(root)
    plan = SourcePlan(metadata, output, root, ContractStore.for_manifest(metadata), manifest_targets(data), packages)
    contested_root = _root_conflicts(metadata, output, root)
    if contested_root:
        return replace(plan, statuses=tuple(contested_root))
    manifest_conflicts, shared = _manifest_conflicts(metadata, data)
    generated_files, generated_conflicts = _generated_files(metadata, output, root)
    ownership = _ownership(root, packages, {target.identity for target in plan.targets}, metadata.name)
    names = _assign_names(plan.targets, {i: p.name for i, p in ownership.owned.items()}, *_occupied(root))
    statuses = [*manifest_conflicts, *generated_conflicts, *ownership.conflicts]
    new_packages: dict[Path, dict[str, str]] = {}
    new_files: dict[Path, str] = {}
    for target in plan.targets:
        if target.identity in shared | ownership.contested:
            continue
        existing = ownership.owned.get(target.identity)
        if existing is not None:
            status, missing = _reconcile_existing(plan, target, existing)
            status = _relocated(plan, data, status)
            new_files.update(missing)
        elif ownership.unreadable:
            continue
        else:
            status, files = _scaffold(plan, target, root / names[target.identity])
            if status.state == "created":
                new_packages[status.path] = files
            else:
                new_files.update({status.path / name: text for name, text in files.items()})
        statuses.append(status)
    statuses += _orphans(plan, data, ownership.owned)
    return replace(
        plan,
        statuses=tuple(statuses),
        new_packages=new_packages,
        new_files=new_files,
        generated_files=generated_files,
    )


def _create_package(directory: Path, files: dict[str, str]) -> list[Path]:
    # Hidden until renamed, so discovery never sees a partial package; mkdir, unlike mkdtemp, keeps umask modes.
    staging = directory.with_name(f".{directory.name}.{secrets.token_hex(6)}")
    staging.mkdir()
    try:
        for name, text in files.items():
            (staging / name).write_text(text, encoding="utf-8")
        if directory.exists() or directory.is_symlink():
            raise ValueError(f"{directory} appeared during generation; nothing was written there")
        staging.rename(directory)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return [directory / name for name in files]


def _create_file(path: Path, text: str) -> bool:
    # Exclusive creation also preserves a file authored while generation ran.
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
    except FileExistsError:
        return False
    return True


def apply_plan(plan: SourcePlan) -> tuple[Path, ...]:
    """Write a conflict-free plan: stage new packages, create missing files, refresh the generated files."""
    if plan.conflicts:
        raise ValueError("; ".join(f"{status.path}: {status.detail}" for status in plan.conflicts))
    taken = sorted(str(directory) for directory in plan.new_packages if directory.exists() or directory.is_symlink())
    if taken:
        raise ValueError(f"Package directories already exist: {taken}; nothing was written")
    plan.root.mkdir(parents=True, exist_ok=True)
    written = [path for directory, files in plan.new_packages.items() for path in _create_package(directory, files)]
    written += [path for path, text in plan.new_files.items() if _create_file(path, text)]
    written += [write_module(path, text) for path, text in plan.generated_files.items()]
    return tuple(written)


def record_revisions(plan: SourcePlan) -> tuple[Path, ...]:
    """Snapshot every target's current revision into the project's contract store."""
    if plan.store is None:
        return ()
    written = (plan.store.record(target.kind, target.definition) for target in plan.targets)
    return tuple(path for path in written if path is not None)


def unrecorded(plan: SourcePlan) -> list[PackageStatus]:
    """Packages whose acknowledged revision is current but was never snapshotted."""
    if plan.store is None:
        return []
    store = plan.store
    return [
        status
        for status in plan.statuses
        if status.state == "current" and status.revision and store.get(status.revision) is None
    ]


def generate_source_packages(metadata: Path, output: Path, package: str | None = None) -> SourcePlan:
    """Reconcile one manifest and write the result: refuse on conflict, create what is missing, record revisions."""
    plan = plan_sources(metadata, output, package)
    apply_plan(plan)
    record_revisions(plan)
    return plan
