"""What static discovery sees under a sources package, and every inventory, selection and revision finding."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from biotope.graph.contracts import Pipeline, SourceContract
from biotope.graph.discovery import Package, Root, discover_packages, discover_roots, generated_root, is_placeholder
from biotope.graph.inventory import PackageStatus, SourcePlan, plan_sources, unrecorded
from biotope.graph.render import relative_path
from biotope.graph.reports import Finding, Location, Severity
from biotope.graph.revisions import DRIFT_LINE_LIMIT, describe_contract, project_root, short_revision
from biotope.graph.sources import KINDS
from biotope.graph.targets import unscoped_fields


@dataclass(frozen=True)
class BrokenRoot:
    """A generated root whose manifest cannot be reconciled; ``problem`` is None when the manifest is gone."""

    root: Root
    packages: tuple[Package, ...]
    problem: str | None = None


@dataclass(frozen=True)
class Survey:
    """What static discovery sees under one sources package, before any project import."""

    sources: Path
    plans: tuple[SourcePlan, ...] = ()
    broken: tuple[BrokenRoot, ...] = ()
    unrooted: tuple[Path, ...] = ()

    @property
    def packages(self) -> tuple[Package, ...]:
        return (
            *(package for plan in self.plans for package in plan.packages),
            *(package for broken in self.broken for package in broken.packages),
        )

    @property
    def schemas(self) -> set[Path]:
        return {package.schema.resolve() for package in self.packages}

    def reports_drift(self, schema: Path, metadata: Path) -> bool:
        """Whether an inventory finding explains how ``schema`` drifted from ``metadata``."""
        return any(
            status.drift is not None
            and (status.path / "schema.py").resolve() == schema.resolve()
            and plan.metadata.resolve() == metadata.resolve()
            for plan in self.plans
            for status in plan.statuses
        )


def survey_sources(sources: Path, project: Path | None = None) -> Survey:
    """Reconcile every generated root under a sources package, without writing or importing."""
    roots = discover_roots(sources)
    plans: list[SourcePlan] = []
    broken: list[BrokenRoot] = []
    for root in roots:
        if not root.metadata.is_file():
            broken.append(BrokenRoot(root, discover_packages(root.path)))
            continue
        try:
            plans.append(plan_sources(root.metadata, sources, root.name))
        except (ValueError, OSError) as exc:
            broken.append(BrokenRoot(root, discover_packages(root.path), f"{type(exc).__name__}: {exc}"))
    unrooted: tuple[Path, ...] = ()
    if project is not None:
        rooted = {root.metadata for root in roots}
        managed = sorted((project / ".biotope/datasets").rglob("*.jsonld"))
        unrooted = tuple(path for path in managed if path.resolve() not in rooted)
    return Survey(sources, tuple(plans), tuple(broken), unrooted)


def sources_of(pipeline: Pipeline) -> tuple[Path, ...]:
    """The sources packages holding the pipeline's registered schemas, laid out as ``<sources>/<root>/<package>``."""
    roots = {contract.schema.resolve().parent.parent for contract in pipeline.source_inventory}
    return tuple(sorted(root.parent for root in roots if generated_root(root) is not None))


def _finding(
    code: str,
    severity: Severity,
    subject: str,
    message: str,
    path: Path | None = None,
    examples: tuple[dict[str, object], ...] = (),
) -> Finding:
    return Finding(code, severity, subject, message, Location(str(path)) if path is not None else None, examples)


@dataclass(frozen=True)
class _Registrations:
    """Every registration of each schema, and what the pipeline selects and excludes."""

    by_schema: Mapping[Path, tuple[SourceContract, ...]]
    selected: tuple[SourceContract, ...] = ()
    excluded: Mapping[str, str] = field(default_factory=dict[str, str])

    @classmethod
    def of(cls, pipeline: Pipeline | None) -> _Registrations:
        if pipeline is None:
            return cls({})
        by_schema: dict[Path, tuple[SourceContract, ...]] = {}
        for contract in pipeline.source_inventory:
            schema = contract.schema.resolve()
            by_schema[schema] = (*by_schema.get(schema, ()), contract)
        return cls(by_schema, pipeline.sources, pipeline.excluded_sources)

    def of_package(self, package: Path) -> tuple[SourceContract, ...]:
        return self.by_schema.get((package / "schema.py").resolve(), ())

    def selects(self, package: Path) -> bool:
        return any(contract in self.selected for contract in self.of_package(package))

    def severity(self, package: Path) -> Severity:
        """A package's findings only warn once every registration of its schema is excluded."""
        registered = self.of_package(package)
        return "warning" if registered and all(item.name in self.excluded for item in registered) else "error"


def _root_findings(survey: Survey, registrations: _Registrations) -> Iterator[Finding]:
    for broken in survey.broken:
        root = broken.root
        if broken.problem is not None:
            message = f"cannot read the manifest of root {root.name}: {broken.problem}"
            yield _finding("inventory.manifest_invalid", "error", root.name, message, root.path)
            continue
        message = f"root {root.name} names {root.metadata}, which no longer exists; its packages are orphans"
        yield _finding("inventory.manifest_missing", "warning", root.name, message, root.path / "__init__.py")
        for package in broken.packages:
            yield _finding(
                "inventory.orphan",
                registrations.severity(package.path),
                f"{root.name}/{package.name}",
                "its manifest is gone; delete the directory to remove this source",
                package.path,
            )
    for path in survey.unrooted:
        message = f"{path} is managed but has no source root; run biotope source generate {path} --out {survey.sources}"
        yield _finding("inventory.manifest_not_generated", "warning", path.name, message, path)


def _status_findings(plan: SourcePlan, status: PackageStatus, registrations: _Registrations) -> Iterator[Finding]:
    subject = f"{plan.root.name}/{status.package}" if status.package else plan.root.name
    if status.state == "conflict":
        yield _finding("inventory.conflict", "error", subject, status.detail, status.path)
    elif status.state in ("created", "completed"):
        what = f"{KINDS[status.kind].label} {status.identity!r}" if status.kind else "a described input"
        message = f"{what} has no complete source package; run {_command(plan)}"
        yield _finding("inventory.stale", "error", subject, message, status.path)
    elif status.state == "orphaned":
        yield _finding("inventory.orphan", registrations.severity(status.path), subject, status.detail, status.path)
    if status.drift is None:
        return
    message = (
        f"{status.identity!r} changed since revision {short_revision(status.acknowledged)} was acknowledged "
        f"(manifest now {short_revision(status.revision)}). Review the change, update the schema, then set "
        f"__source_digest__ to {status.revision!r}:\n" + "\n".join(status.drift.lines(DRIFT_LINE_LIMIT))
    )
    examples = tuple(change.to_json() for change in status.drift.changes)
    schema = status.path / "schema.py"
    yield _finding("source.drift", registrations.severity(status.path), subject, message, schema, examples)
    if not status.drift.available:
        [target] = [target for target in plan.targets if target.identity == status.identity]
        message = (
            "the acknowledged revision is not recorded, so the change cannot be itemized; the current contract is:\n"
            + "\n".join(describe_contract(target.definition))
        )
        yield _finding("source.revision_unavailable", "warning", subject, message, schema)


def _unscoped_findings(plan: SourcePlan, registrations: _Registrations) -> Iterator[Finding]:
    packages = {package.path: package for package in plan.packages}
    owners = {
        status.identity: packages[status.path]
        for status in plan.statuses
        if status.state in ("current", "drift") and status.identity is not None
    }
    for target in plan.targets:
        package = owners.get(target.identity)
        if package is None or package.declaration.field_refs or not registrations.selects(package.path):
            continue
        for reference in unscoped_fields(target):
            yield _finding(
                "source.unscoped_field",
                "error",
                f"{plan.root.name}/{package.name}",
                f"field @id {reference!r} is not scoped under {target.identity + '/'!r}; "
                "rescope it in the manifest (or bind it with __field_refs__)",
                package.schema,
            )


def _command(plan: SourcePlan) -> str:
    project = project_root(plan.metadata)
    manifest = relative_path(plan.metadata, project) if project is not None else plan.metadata.name
    return f"biotope source generate {manifest} --out {plan.sources} --package {plan.root.name}"


def _plan_findings(plan: SourcePlan, registrations: _Registrations) -> Iterator[Finding]:
    for status in plan.statuses:
        yield from _status_findings(plan, status, registrations)
    for status in unrecorded(plan):
        yield _finding(
            "source.revision_unrecorded",
            "warning",
            f"{plan.root.name}/{status.package}",
            f"revision {short_revision(status.revision)} is acknowledged but not recorded; run {_command(plan)}",
            status.path / "schema.py",
        )
    for path in plan.generated_files:
        message = f"{path.name} is missing or not in the current generated form; run {_command(plan)}"
        yield _finding("inventory.stale", "error", plan.root.name, message, path)
    yield from _unscoped_findings(plan, registrations)


def _registration_findings(
    surveys: tuple[Survey, ...], pipeline: Pipeline, registrations: _Registrations
) -> Iterator[Finding]:
    inventory = pipeline.source_inventory
    discovered = {schema for survey in surveys for schema in survey.schemas}
    if not inventory and (pipeline.sources or discovered):
        what = "sources are selected" if pipeline.sources else f"{len(discovered)} source packages exist"
        message = f"{what} but source_inventory is empty; pass source_inventory=INVENTORY"
        yield _finding("inventory.absent", "error", pipeline.name, message)
    for name, count in Counter(contract.name for contract in inventory).items():
        if count > 1:
            yield _finding("inventory.mismatch", "error", name, f"{count} inventoried sources share the name {name!r}")
    for path, registered in sorted(registrations.by_schema.items()):
        names = sorted({contract.name for contract in registered})
        if len(names) > 1:
            message = "one schema is registered as " + ", ".join(repr(name) for name in names)
            yield _finding("inventory.mismatch", "error", names[0], message, path)
    if not surveys or not inventory:
        return
    surveyed = [survey.sources.resolve() for survey in surveys]
    registered_here = {path for path in registrations.by_schema if any(path.is_relative_to(s) for s in surveyed)}
    for path in sorted(discovered - registered_here):
        yield _finding(
            "inventory.mismatch",
            "error",
            f"{path.parent.parent.name}/{path.parent.name}",
            "a discovered source package is missing from source_inventory; pass source_inventory=INVENTORY",
            path.parent,
        )
    for path in sorted(registered_here - discovered):
        message = "source_inventory registers a schema no generated root contains"
        yield _finding("inventory.mismatch", "error", registrations.by_schema[path][0].name, message, path)


def _selection_findings(pipeline: Pipeline) -> Iterator[Finding]:
    known = {contract.name: contract for contract in pipeline.source_inventory}
    chosen = {source.name: source for source in pipeline.sources}
    excluded = pipeline.excluded_sources
    for name, source in chosen.items():
        if known and name not in known:
            yield _finding("inventory.mismatch", "error", name, "a selected source is missing from source_inventory")
        elif known and source != known[name]:
            yield _finding(
                "inventory.mismatch", "error", name, "the selected contract differs from its inventory entry"
            )
    for name in sorted(set(known) - set(chosen) - set(excluded)):
        message = "neither selected nor excluded; select it or add it to EXCLUDED_SOURCES with a reason"
        yield _finding("inventory.unselected", "error", name, message)
    for name in sorted(set(chosen) & set(excluded)):
        yield _finding("inventory.conflicting_selection", "error", name, "both selected and excluded")
    for name in sorted(set(excluded) - set(known)):
        yield _finding("inventory.unknown_exclusion", "error", name, "this exclusion names no inventoried source")
    for name, reason in sorted(excluded.items()):
        if not reason.strip():
            yield _finding("inventory.exclusion_reason", "error", name, "an exclusion needs a reason")
    for name, source in sorted(chosen.items()):
        loader = source.schema.parent / "loader.py"
        if is_placeholder(loader):
            message = (
                "the selected loader is still a placeholder; implement it and delete its first line, or exclude "
                "the source"
            )
            yield _finding("inventory.placeholder", "error", name, message, loader)


def inventory_findings(surveys: tuple[Survey, ...], pipeline: Pipeline | None) -> list[Finding]:
    """Every inventory, selection and revision finding, none hiding another; without a pipeline, the static ones."""
    registrations = _Registrations.of(pipeline)
    findings: list[Finding] = []
    for survey in surveys:
        findings += _root_findings(survey, registrations)
        for plan in survey.plans:
            findings += _plan_findings(plan, registrations)
    if pipeline is not None:
        findings += [*_registration_findings(surveys, pipeline, registrations), *_selection_findings(pipeline)]
    return findings
