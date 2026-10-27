"""Add command implementation for tracking data files and metadata."""

from __future__ import annotations

import json
import shlex
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from glob import escape as escape_glob
from pathlib import Path
from typing import Any

import click

from biotope.commands._add_output import AddOutput
from biotope.croissant import annotation
from biotope.croissant.ids import note_moves, stable_ids
from biotope.extraction.run import state_path
from biotope.graph.moves import carry_description, kept, package_files
from biotope.graph.sources import refresh_description, write_description, write_text_atomic
from biotope.metadata import (
    DERIVED_FROM,
    FILE_OBJECT_TYPE,
    STATUS,
    add_derived_from,
    classify_status_from_baker,
    dataset_id,
    make_file_object,
    manifest_for,
    merge_metadata,
    normalize_metadata_shape,
    parse_key_value_pairs,
    resolve_content_url,
    resolve_target,
    set_status,
)
from biotope.utils import (
    calculate_file_checksum,
    find_biotope_root,
    is_file_tracked,
    load_project_metadata,
    warn_ignored,
)


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--rebake", is_flag=True, help="Describe an already-tracked dataset again from its data and annotation file"
)
@click.option("--json", "as_json", is_flag=True, help="Emit a complete machine-readable scan report on stdout")
@click.option("--name", help="Dataset name override")
@click.option("--description", help="Dataset description override")
@click.option("--license", "license_value", help="Dataset license")
@click.option("--creator", help="Dataset creator name")
@click.option("--creator-email", help="Dataset creator email")
@click.option("--url", help="Dataset URL")
@click.option("--citation", help="Dataset citation text")
@click.option("--version", help="Dataset version")
@click.option("--keyword", "keywords", multiple=True, help="Dataset keyword (repeatable)")
@click.option("--access-restrictions", help="Dataset access restrictions")
@click.option("--legal-obligations", help="Dataset legal obligations")
@click.option("--collaboration-partner", help="Dataset collaboration partner")
@click.option("--rai", "rai_pairs", multiple=True, help="Croissant RAI field as KEY=VALUE")
@click.option(
    "--status",
    "status_override",
    type=click.Choice(["raw", "processed"]),
    default=None,
    help=(
        "Override workflow state. Default: 'processed' when fields are described, "
        "'raw' otherwise. This does not validate values."
    ),
)
@click.option(
    "--derived-from",
    "derived_from",
    multiple=True,
    help="Record this dataset as derived from another (repeatable). Pass a "
    "dataset reference — data path, manifest path, or dataset name.",
)
def add(
    paths: tuple[Path, ...],
    rebake: bool,
    as_json: bool,
    name: str | None,
    description: str | None,
    license_value: str | None,
    creator: str | None,
    creator_email: str | None,
    url: str | None,
    citation: str | None,
    version: str | None,
    keywords: tuple[str, ...],
    access_restrictions: str | None,
    legal_obligations: str | None,
    collaboration_partner: str | None,
    rai_pairs: tuple[str, ...],
    status_override: str | None,
    derived_from: tuple[str, ...],
) -> None:
    """Add data files or rooted directories to a biotope project."""
    with AddOutput(as_json) as reporter:
        if not paths:
            ctx = click.get_current_context()
            click.echo(ctx.get_help())
            raise click.Abort

        if name and len(paths) != 1:
            raise click.BadParameter("--name can only be used when adding one path.")

        biotope_root = find_biotope_root()
        if not biotope_root:
            raise click.ClickException("Not in a biotope project. Run 'biotope init' first.")
        reporter.root = biotope_root

        try:
            rai_fields = parse_key_value_pairs(rai_pairs, "--rai")
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc

        try:
            resolved_provenance = [resolve_dataset_ref(ref, biotope_root) for ref in derived_from]
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc

        given = {
            key: value
            for key, value in (
                ("name", name),
                ("description", description),
                ("license", license_value),
                ("url", url),
                ("citeAs", citation),
                ("version", version),
                ("cr:accessRestrictions", access_restrictions),
                ("cr:legalObligations", legal_obligations),
                ("cr:collaborationPartner", collaboration_partner),
            )
            if value is not None
        }
        if creator is not None or creator_email is not None:
            given["creator"] = {key: value for key, value in (("name", creator), ("email", creator_email)) if value}
        if keywords:
            given["keywords"] = list(keywords)
        given.update(rai_fields)
        if status_override is not None:
            given[STATUS] = status_override
        if resolved_provenance:
            given[DERIVED_FROM] = resolved_provenance

        datasets_dir = biotope_root / ".biotope" / "datasets"
        datasets_dir.mkdir(parents=True, exist_ok=True)

        added_entries: list[Path] = []
        for path in paths:
            if path.is_file():
                if add_file(path, biotope_root, datasets_dir, rebake, given=given, reporter=reporter):
                    added_entries.append(path)
                continue

            target = resolve_target(path, biotope_root)
            if target.metadata_path.exists() and not rebake:
                reporter.skipped(
                    path, f"{target.metadata_path.relative_to(biotope_root)} already exists; use --rebake to refresh."
                )
                continue
            if _bake_directory(path, biotope_root, given=given, reporter=reporter) is not None:
                added_entries.append(path)

        for entry in added_entries:
            manifest = resolve_target(entry.resolve(), biotope_root).metadata_path
            warn_ignored(biotope_root, [manifest, annotation.annotation_path(entry.resolve())])
            reporter.row("Next", f"biotope map inspect {shlex.quote(str(manifest.relative_to(biotope_root)))}")
        if any(source["status"] == "failed" for source in reporter.sources):
            raise click.ClickException("One or more inputs could not be baked.")


def add_file(
    file_path: Path,
    biotope_root: Path,
    datasets_dir: Path,
    force: bool,
    overrides: dict[str, Any] | None = None,
    *,
    given: dict[str, Any] | None = None,
    reporter: AddOutput | None = None,
) -> bool:
    """Add a single file to the biotope project."""
    overrides = overrides or {}
    reporter = reporter or AddOutput()
    reporter.root = biotope_root
    abs_file = file_path.resolve()
    try:
        relative_path = abs_file.relative_to(biotope_root)
    except ValueError:
        reporter.skipped(file_path, "Outside the biotope project.")
        return False

    if not force and is_file_tracked(abs_file, biotope_root):
        reporter.skipped(file_path, "Already tracked; use --rebake to refresh.")
        return False

    defaults = load_project_metadata(biotope_root)
    now = datetime.now(tz=timezone.utc).isoformat()
    metadata = merge_metadata(
        {
            "name": overrides.get("name") or str(relative_path),
            "description": (
                overrides.get("description") or defaults.get("description") or f"Dataset for {abs_file.name}"
            ),
            "distribution": [make_file_object(abs_file, abs_file.parent)],
            "dateCreated": now,
        }
    )

    _enrich_with_baker(metadata, abs_file, reporter=reporter)
    _give_stable_ids(metadata, relative_path, abs_file)
    # Baker's single-file assembly is rooted at the file's parent. File tracking
    # in a single-file manifest uses project-relative paths.
    parent = abs_file.parent.relative_to(biotope_root)
    for distribution in metadata.get("distribution", []):
        if distribution.get("contentUrl"):
            distribution["contentUrl"] = str(parent / distribution["contentUrl"])
        if distribution.get("includes"):
            includes = distribution["includes"]
            distribution["includes"] = (
                str(parent / includes) if isinstance(includes, str) else [str(parent / pattern) for pattern in includes]
            )
    _apply_dataset_metadata(metadata, defaults, overrides)
    _apply_pipeline_state(metadata, overrides)
    manifest = resolve_target(abs_file, biotope_root).metadata_path
    previous = manifest if manifest.exists() else _gone_copy(abs_file, biotope_root)
    if previous is not None:
        note_moves(_read_description(previous), metadata)
    if previous in (None, manifest):
        _describe(abs_file, manifest, metadata, given, reporter)
    else:
        _take_over(previous, abs_file, manifest, metadata, given, biotope_root, reporter)
    return True


def _gone_copy(data: Path, biotope_root: Path) -> Path | None:
    checksum = calculate_file_checksum(data)
    descriptions = sorted((biotope_root / ".biotope" / "datasets").rglob("*.jsonld"))
    found = [path for path in descriptions if _describes_gone_copy(path, checksum, biotope_root)]
    return found[0] if len(found) == 1 else None


def _take_over(
    previous: Path,
    data: Path,
    manifest: Path,
    baked: dict[str, Any],
    given: dict[str, Any] | None,
    biotope_root: Path,
    reporter: AddOutput,
) -> None:
    gone = biotope_root / dataset_id(previous, biotope_root)
    left, notes = annotation.annotation_path(gone), annotation.annotation_path(data)
    carried = {left: notes} if left.is_file() and not notes.exists() else {}
    try:
        annotation.current(baked, annotation.read(next(iter(carried), notes)))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    with kept([previous, manifest, notes, *carried, *package_files(biotope_root / "graph/sources", previous)]):
        warn_ignored(biotope_root, carry_description(biotope_root, previous, manifest))
        for old, new in carried.items():
            shutil.move(old, new)
        _describe(data, manifest, baked, given, reporter)
    reporter.warning(
        data,
        f"{gone.relative_to(biotope_root)} is gone and this file has its content, so its description now "
        "describes this file and source generate reports each ID that changed. Move described files with biotope mv",
    )


def _read_description(path: Path) -> dict[str, Any]:
    try:
        described = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return described if isinstance(described, dict) else {}


def _describes_gone_copy(description: Path, checksum: str, biotope_root: Path) -> bool:
    data = dataset_id(description, biotope_root)
    if (biotope_root / data).exists():
        return False
    described = _read_description(description)
    files = [entry for entry in described.get("distribution") or [] if entry.get("@type") == FILE_OBJECT_TYPE]
    return [(entry.get("contentUrl"), entry.get("sha256")) for entry in files] == [(data, checksum)]


def _describe(
    data: Path, manifest: Path, baked: dict[str, Any], given: dict[str, Any] | None, reporter: AddOutput
) -> None:
    try:
        if given is not None:
            path = annotation.annotation_path(data)
            if given or not path.exists():
                write_text_atomic(path, annotation.edited(path, (), given))
            reporter.annotation(data, path)
        described = write_description(manifest, baked)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    reporter.saved(manifest, described)
    found = annotation.located(manifest)
    unknown = annotation.unknown(baked, annotation.read(found)) if found is not None else []
    if unknown:
        reporter.warning(data, f"{found} names what the data does not have: {', '.join(unknown)}")


def _enrich_with_baker(metadata: dict[str, Any], file_path: Path, *, reporter: AddOutput | None = None) -> None:
    """Use baker's full assembly, scoped to exactly this file."""
    bake_error = None
    reporter = reporter or AddOutput()
    with reporter.scan(file_path, file_path.parent) as report:
        from croissant_baker.metadata_generator import MetadataGenerator

        pattern = escape_glob(file_path.name)
        generator = MetadataGenerator(
            dataset_path=str(file_path.parent),
            name=metadata.get("name") or file_path.name,
            includes=[pattern],
            excludes=[f"*/{pattern}"],
        )
        report.attach(generator)
        try:
            baked = normalize_metadata_shape(generator.generate_metadata(progress_callback=report))
        except ValueError as exc:
            bake_error = exc
        else:
            for key, value in baked.items():
                if key not in {"name", "description", "dateCreated"}:
                    metadata[key] = value
        report.finish(generator.scan_report.to_dict(), {})
    if bake_error is not None and str(bake_error) != "No supported files found in the dataset":
        report.result.update(status="failed", error=str(bake_error))
        raise bake_error


def _apply_dataset_metadata(metadata: dict[str, Any], defaults: dict[str, Any], overrides: dict[str, Any]) -> None:
    for key in ("creator", "license"):
        if defaults.get(key):
            metadata[key] = defaults[key]
        else:
            metadata.pop(key, None)
    for key in ("name", "description"):
        if overrides.get(key) is not None:
            metadata[key] = overrides[key]
    for key in ("url", "citation"):
        if key not in metadata and defaults.get(key):
            metadata[key] = defaults[key]
    for key in ("cr:projectName", "cr:accessRestrictions", "cr:legalObligations", "cr:collaborationPartner"):
        if defaults.get(key):
            metadata[key] = defaults[key]


def _bake_directory(
    directory: Path,
    biotope_root: Path,
    *,
    given: dict[str, Any] | None = None,
    reporter: AddOutput | None = None,
) -> tuple[dict[str, Any], int] | None:
    """Run croissant-baker over ``directory`` and write one directory-level JSON-LD."""
    reporter = reporter or AddOutput()
    reporter.root = biotope_root
    abs_dir = directory.resolve()
    try:
        rel_dir = abs_dir.relative_to(biotope_root)
    except ValueError:
        reporter.skipped(directory, "Outside the biotope project.")
        return None

    target = resolve_target(abs_dir, biotope_root)
    defaults = load_project_metadata(biotope_root)
    now = datetime.now(tz=timezone.utc).isoformat()

    found = sorted(_iter_directory_files(abs_dir))
    records = [path for path in found if state_path(biotope_root, path).is_file()]
    files = [path for path in found if path not in records]
    described = {
        abs_dir / entry["contentUrl"]
        for entry in _read_description(target.metadata_path).get("distribution") or []
        if entry.get("@type") == FILE_OBJECT_TYPE and isinstance(entry.get("contentUrl"), str)
    }
    copies = _identical_copies(files, described)
    skipped = {**{copy: "the identical copy" for copy in copies}, **{path: "the extracted records" for path in records}}
    excluded = {escape_glob(str(path.relative_to(abs_dir))): path for path in skipped}
    bake_error = None
    with reporter.scan(abs_dir, abs_dir) as report:
        for relative in (path.relative_to(abs_dir) for path in files if path not in copies):
            caught = next((copy for pattern, copy in excluded.items() if relative.match(pattern)), None)
            if caught is not None:
                reporter.warning(
                    abs_dir,
                    f"{relative} was not parsed: croissant-baker matches exclusions by path suffix, "
                    f"so skipping {skipped[caught]} {caught.relative_to(abs_dir)} also skipped it",
                )
        try:
            from croissant_baker.metadata_generator import MetadataGenerator
        except ImportError as exc:
            raise click.ClickException("croissant-baker is unavailable; check its installation.") from exc

        generator = MetadataGenerator(
            dataset_path=str(abs_dir),
            name=str(rel_dir),
            description=defaults.get("description"),
            url=defaults.get("url"),
            citation=defaults.get("citation"),
            date_created=now,
            excludes=[
                annotation.FOLDER_FILE,
                f"**/{annotation.FOLDER_FILE}",
                f"*{annotation.SUFFIX}",
                f"**/*{annotation.SUFFIX}",
                ".biotope/**",
                "**/.biotope/**",
                ".git/**",
                "**/.git/**",
                *excluded,
            ],
        )
        report.attach(generator)

        try:
            metadata_dict = normalize_metadata_shape(generator.generate_metadata(progress_callback=report))
        except ValueError as exc:
            bake_error = exc
        report.finish(generator.scan_report.to_dict(), copies)

    if bake_error is not None:
        if str(bake_error) != "No supported files found in the dataset":
            report.result.update(status="failed", error=str(bake_error))
            reporter.row("FAIL", str(rel_dir), str(bake_error))
            return None
        metadata_dict = _build_minimal_directory_metadata(abs_dir, biotope_root, defaults)

    metadata_dict.setdefault("dateCreated", now)
    _apply_dataset_metadata(metadata_dict, defaults, {})
    _register_distinct_files(metadata_dict, abs_dir, biotope_root, files, copies)
    _give_stable_ids(metadata_dict, rel_dir, abs_dir)
    if target.metadata_path.is_file():
        note_moves(refresh_description(target.metadata_path), metadata_dict)
    _apply_pipeline_state(metadata_dict, {})
    _describe(abs_dir, target.metadata_path, metadata_dict, given, reporter)
    return metadata_dict, len(files)


def _build_minimal_directory_metadata(abs_dir: Path, biotope_root: Path, defaults: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal dataset for directories without baker-supported files."""
    relative_dir = abs_dir.relative_to(biotope_root)
    return merge_metadata(
        {
            "name": str(relative_dir),
            "description": defaults.get("description") or f"Dataset for {relative_dir}",
            "distribution": [],
        }
    )


def _identical_copies(files: list[Path], described: set[Path]) -> dict[Path, Path]:
    by_size: dict[int, list[Path]] = defaultdict(list)
    for file_path in sorted(files, key=lambda path: path not in described):
        by_size[file_path.stat().st_size].append(file_path)
    copies: dict[Path, Path] = {}
    for paths in by_size.values():
        originals: dict[str, Path] = {}
        for file_path in paths if len(paths) > 1 else ():
            original = originals.setdefault(calculate_file_checksum(file_path), file_path)
            if original != file_path and file_path not in described:
                copies[file_path] = original
    return copies


def _patterns(value: str | list[str] | None) -> list[str]:
    return [value] if isinstance(value, str) else list(value or [])


def _register_distinct_files(
    metadata_dict: dict[str, Any],
    abs_dir: Path,
    biotope_root: Path,
    files: list[Path],
    copies: dict[Path, Path],
) -> None:
    """Add file pointers for distinct files croissant-baker left out, and keep identical copies out of FileSets."""
    distributions = metadata_dict.setdefault("distribution", [])
    covered: set[Path] = set()
    for item in distributions:
        if item.get("@type") == FILE_OBJECT_TYPE and item.get("contentUrl"):
            path = resolve_content_url(item["contentUrl"], abs_dir, biotope_root)
            if path is not None and path.is_file():
                covered.add(path.resolve())
        elif item.get("@type") == "cr:FileSet":
            members = {
                candidate
                for pattern in _patterns(item.get("includes"))
                for candidate in abs_dir.glob(pattern)
                if candidate.is_file()
            }
            covered.update(member.resolve() for member in members)
            skipped = sorted(escape_glob(str(member.relative_to(abs_dir))) for member in members if member in copies)
            if skipped:
                item["excludes"] = [*_patterns(item.get("excludes")), *skipped]
    for file_path in files:
        if file_path not in copies and file_path.resolve() not in covered:
            distributions.append(make_file_object(file_path, abs_dir))


def _give_stable_ids(metadata: dict[str, Any], source: Path, data: Path) -> None:
    try:
        annotation.name_file_sets(metadata, annotation.read(annotation.annotation_path(data)))
        stable_ids(metadata)
    except ValueError as exc:
        raise click.ClickException(f"{source}: {exc}") from exc


def _iter_directory_files(abs_dir: Path):
    """Yield physical data files under a rooted directory, skipping biotope-owned paths."""
    for file_path in abs_dir.rglob("*"):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(abs_dir)
        if any(part.startswith(".") for part in relative.parts) or file_path.name.endswith(annotation.SUFFIX):
            continue
        yield file_path


def _apply_pipeline_state(metadata: dict[str, Any], overrides: dict[str, Any]) -> None:
    """Stamp ``biotope:status`` + ``prov:wasDerivedFrom`` on a fresh manifest.

    Status: explicit ``--status`` override wins; otherwise classify from the
    baked Croissant (record set with field listing → processed, else raw).
    Provenance: each ``--derived-from`` ref is added idempotently.
    """
    status = overrides.get("status_override") or classify_status_from_baker(metadata)
    set_status(metadata, status)
    for source_id in overrides.get("derived_from") or []:
        add_derived_from(metadata, source_id)


def resolve_dataset_ref(ref: str, biotope_root: Path) -> str:
    """Normalise a user-supplied dataset reference to its canonical id.

    A dataset's canonical id is its relative path under ``.biotope/datasets/``
    sans the ``.jsonld`` suffix — the same key biotope already uses to mirror
    manifests onto the data tree. Accepts:

    * the canonical id itself (``"data/kidney_pdf"``),
    * a path to the data file/dir,
    * a path to the ``.jsonld`` manifest.

    Raises ``ValueError`` when nothing resolves.
    """
    datasets_dir = biotope_root / ".biotope" / "datasets"
    if (datasets_dir / f"{ref}.jsonld").is_file():
        return ref
    p = (biotope_root / ref).resolve()
    if p.is_relative_to(datasets_dir) and p.suffix == ".jsonld" and p.is_file():
        return dataset_id(p, biotope_root)
    if not p.is_relative_to(biotope_root):
        raise ValueError(f"--derived-from {ref!r}: path is outside the biotope project")
    if manifest_for(p, biotope_root).is_file():
        return p.relative_to(biotope_root).as_posix()

    msg = (
        f"--derived-from {ref!r}: no manifest found under .biotope/datasets/. "
        "Pass a dataset name (e.g. 'data/kidney_pdf'), a data path, or a "
        ".jsonld path of an existing dataset."
    )
    raise ValueError(msg)
