"""Add command implementation for tracking data files and metadata."""

from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime, timezone
from glob import escape as escape_glob
from pathlib import Path
from typing import Any

import click
import yaml

from biotope.commands._add_output import AddOutput
from biotope.graph.sources import protect_curated, write_text_atomic
from biotope.metadata import (
    FILE_OBJECT_TYPE,
    SCAFFOLD_FILENAME,
    add_derived_from,
    classify_status_from_baker,
    make_file_object,
    merge_metadata,
    normalize_metadata_shape,
    parse_key_value_pairs,
    resolve_content_url,
    resolve_target,
    set_status,
)
from biotope.utils import (
    find_biotope_root,
    is_file_tracked,
    load_project_metadata,
    stage_git_changes,
)


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--force", "-f", is_flag=True, help="Force add even if file already tracked")
@click.option("--rebake", is_flag=True, help="Refresh an already-tracked directory's manifest from disk")
@click.option("--json", "as_json", is_flag=True, help="Emit a complete machine-readable scan report on stdout")
@click.option(
    "--bake-to",
    type=click.Path(path_type=Path),
    help="Bake one input to a new review file without changing managed metadata or tracking",
)
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
    force: bool,
    rebake: bool,
    as_json: bool,
    bake_to: Path | None,
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
            resolved_provenance = [_resolve_dataset_ref(ref, biotope_root) for ref in derived_from]
        except ValueError as exc:
            raise click.BadParameter(str(exc)) from exc

        overrides = {
            "name": name,
            "description": description,
            "license": license_value,
            "creator": creator,
            "creator_email": creator_email,
            "url": url,
            "citation": citation,
            "version": version,
            "keywords": list(keywords),
            "access_restrictions": access_restrictions,
            "legal_obligations": legal_obligations,
            "collaboration_partner": collaboration_partner,
            "rai_fields": rai_fields,
            "status_override": status_override,
            "derived_from": resolved_provenance,
        }

        datasets_dir = biotope_root / ".biotope" / "datasets"
        if bake_to is not None:
            if len(paths) != 1 or force or rebake:
                raise click.BadParameter("--bake-to requires one input and cannot be combined with --force or --rebake")
            destination = bake_to.resolve()
            source = paths[0].resolve()
            if destination.exists() or destination.is_relative_to(datasets_dir.resolve()):
                raise click.BadParameter("--bake-to must name a new file outside .biotope/datasets")
            if source.is_dir() and destination.is_relative_to(source):
                raise click.BadParameter("--bake-to must be outside the input directory")
            if source.is_file():
                success = _add_file(
                    source, biotope_root, datasets_dir, False, overrides, output=destination, reporter=reporter
                )
            else:
                success = (
                    _bake_directory(source, biotope_root, overrides, output=destination, reporter=reporter) is not None
                )
            if not success:
                raise click.ClickException("Review bake failed; managed metadata was not changed")
            reporter.sources[-1]["status"] = "review"
            reporter.row("Next", "Reconcile the review bake, then use biotope source register --replace.")
            return
        datasets_dir.mkdir(parents=True, exist_ok=True)

        added_entries: list[Path] = []
        baked_dirs: list[tuple[Path, dict[str, Any]]] = []

        for path in paths:
            if path.is_file():
                result = _add_file(path, biotope_root, datasets_dir, force, overrides, reporter=reporter)
                if result:
                    added_entries.append(path)
                continue

            target = resolve_target(path, biotope_root)
            already_tracked = target.metadata_path.exists()
            if already_tracked and not force and not rebake:
                reporter.skipped(
                    path, f"{target.metadata_path.relative_to(biotope_root)} already exists; use --rebake to refresh."
                )
                continue

            baked = _bake_directory(path, biotope_root, overrides, reporter=reporter)
            if baked is None:
                continue

            metadata_dict, _n_source_files = baked
            added_entries.append(path)
            baked_dirs.append((path.resolve(), metadata_dict))

        if added_entries:
            stage_git_changes(biotope_root)

        for source_dir, metadata_dict in baked_dirs:
            _generate_biotope_scaffold_from_baked(source_dir, metadata_dict, biotope_root, reporter=reporter)

        if added_entries:
            if baked_dirs:
                for source_dir, _metadata_dict in baked_dirs:
                    if any(
                        s.get("annotation_template") and s["input"] == reporter.path(source_dir)
                        for s in reporter.sources
                    ):
                        reporter.row(
                            "Apply", f"biotope annotate apply {shlex.quote(str(source_dir.relative_to(biotope_root)))}"
                        )
            else:
                for entry in added_entries:
                    manifest = resolve_target(entry.resolve(), biotope_root).metadata_path.relative_to(biotope_root)
                    reporter.row("Next", f"biotope map inspect {shlex.quote(str(manifest))}")
        if any(source["status"] == "failed" for source in reporter.sources):
            raise click.ClickException("One or more inputs could not be baked.")


def _add_file(
    file_path: Path,
    biotope_root: Path,
    datasets_dir: Path,
    force: bool,
    overrides: dict[str, Any] | None = None,
    *,
    output: Path | None = None,
    reporter: AddOutput | None = None,
) -> bool:
    """Add a single file to the biotope project."""
    overrides = overrides or _default_overrides()
    reporter = reporter or AddOutput()
    reporter.root = biotope_root
    abs_file = file_path.resolve()
    try:
        relative_path = abs_file.relative_to(biotope_root)
    except ValueError:
        reporter.skipped(file_path, "Outside the biotope project.")
        return False

    if output is None and not force and is_file_tracked(abs_file, biotope_root):
        reporter.skipped(file_path, "Already tracked; use --force to override.")
        return False

    try:
        if output is None:
            protect_curated(resolve_target(abs_file, biotope_root).metadata_path)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    defaults = load_project_metadata(biotope_root)
    now = datetime.now(tz=timezone.utc).isoformat()
    metadata = merge_metadata(
        {
            "name": overrides.get("name") or str(relative_path),
            "description": (
                overrides.get("description") or defaults.get("description") or f"Dataset for {abs_file.name}"
            ),
            "distribution": [make_file_object(abs_file, biotope_root)],
            "dateCreated": now,
        }
    )

    _enrich_with_baker(metadata, abs_file, reporter=reporter)
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
    _apply_dataset_metadata(metadata, defaults, overrides, biotope_root)
    _apply_pipeline_state(metadata, overrides)

    target = resolve_target(abs_file, biotope_root)
    write_text_atomic(output or target.metadata_path, json.dumps(metadata, indent=2) + "\n")
    reporter.saved(output or target.metadata_path, metadata)

    return True


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
        report.finish(generator.scan_report.to_dict())
    if bake_error is not None:
        if str(bake_error) != "No supported files found in the dataset":
            report.result.update(status="failed", error=str(bake_error))
            raise bake_error
        # Keep the original file-tracking pointer, without claiming structure.
        metadata["distribution"][0]["contentUrl"] = file_path.name


def _git_user_identity(cwd: Path) -> tuple[str | None, str | None]:
    """Return (name, email) from git config, preferring repo-local config."""
    try:
        name = subprocess.run(
            ["git", "config", "--get", "user.name"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        email = subprocess.run(
            ["git", "config", "--get", "user.email"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except FileNotFoundError:
        return None, None

    if not isinstance(name, str):
        name = None
    if not isinstance(email, str):
        email = None

    return (name or None), (email or None)


def _apply_dataset_metadata(
    metadata: dict[str, Any],
    defaults: dict[str, Any],
    overrides: dict[str, Any],
    biotope_root: Path,
) -> None:
    """Apply top-level dataset metadata from project defaults and CLI overrides."""
    creator_node = _resolve_creator(defaults, overrides, biotope_root)
    if creator_node:
        metadata["creator"] = creator_node

    field_mapping = {
        "name": "name",
        "description": "description",
        "url": "url",
        "license": "license",
        "citation": "citation",
        "version": "version",
    }
    for override_key, metadata_key in field_mapping.items():
        value = overrides.get(override_key)
        if value is not None:
            metadata[metadata_key] = value
        elif metadata_key not in metadata and defaults.get(metadata_key):
            metadata[metadata_key] = defaults[metadata_key]

    if overrides.get("keywords"):
        metadata["keywords"] = list(overrides["keywords"])

    extension_mapping = {
        "cr:projectName": defaults.get("cr:projectName"),
        "cr:accessRestrictions": overrides.get("access_restrictions")
        if overrides.get("access_restrictions") is not None
        else defaults.get("cr:accessRestrictions"),
        "cr:legalObligations": overrides.get("legal_obligations")
        if overrides.get("legal_obligations") is not None
        else defaults.get("cr:legalObligations"),
        "cr:collaborationPartner": overrides.get("collaboration_partner")
        if overrides.get("collaboration_partner") is not None
        else defaults.get("cr:collaborationPartner"),
    }
    for key, value in extension_mapping.items():
        if value:
            metadata[key] = value

    for key, value in overrides.get("rai_fields", {}).items():
        metadata[key] = value


def _resolve_creator(
    defaults: dict[str, Any],
    overrides: dict[str, Any],
    biotope_root: Path,
) -> dict[str, str] | None:
    """Resolve creator info from CLI, git, or project defaults."""
    default_creator = defaults.get("creator")
    default_name = default_creator.get("name") if isinstance(default_creator, dict) else None

    git_name, git_email = _git_user_identity(biotope_root)

    creator_name = overrides.get("creator") or default_name or git_name or overrides.get("creator_email")
    creator_email = overrides.get("creator_email") or git_email

    if not creator_name:
        return None

    creator_node = {"@type": "Person", "name": creator_name}
    if creator_email:
        creator_node["email"] = creator_email
    return creator_node


def _creator_for_baker(
    defaults: dict[str, Any],
    overrides: dict[str, Any],
    biotope_root: Path,
) -> list[dict[str, str]] | None:
    """Resolve creator info in croissant-baker's expected shape."""
    creator_node = _resolve_creator(defaults, overrides, biotope_root)
    if creator_node is None:
        return None
    return [{key: value for key, value in creator_node.items() if key in {"name", "email", "url"}}]


def _bake_directory(
    directory: Path,
    biotope_root: Path,
    overrides: dict[str, Any] | None = None,
    *,
    output: Path | None = None,
    reporter: AddOutput | None = None,
) -> tuple[dict[str, Any], int] | None:
    """Run croissant-baker over ``directory`` and write one directory-level JSON-LD."""
    overrides = overrides or _default_overrides()
    reporter = reporter or AddOutput()
    reporter.root = biotope_root
    abs_dir = directory.resolve()
    try:
        rel_dir = abs_dir.relative_to(biotope_root)
    except ValueError:
        reporter.skipped(directory, "Outside the biotope project.")
        return None

    target = resolve_target(abs_dir, biotope_root)
    try:
        if output is None:
            protect_curated(target.metadata_path)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    defaults = load_project_metadata(biotope_root)
    now = datetime.now(tz=timezone.utc).isoformat()

    bake_error = None
    with reporter.scan(abs_dir, abs_dir) as report:
        try:
            from croissant_baker.metadata_generator import MetadataGenerator
        except ImportError as exc:
            raise click.ClickException("croissant-baker is unavailable; check its installation.") from exc

        generator = MetadataGenerator(
            dataset_path=str(abs_dir),
            name=overrides.get("name") or str(rel_dir),
            description=overrides.get("description") or defaults.get("description"),
            url=overrides.get("url") or defaults.get("url"),
            license=overrides.get("license") or defaults.get("license"),
            citation=overrides.get("citation") or defaults.get("citation"),
            version=overrides.get("version"),
            date_created=now,
            creators=_creator_for_baker(defaults, overrides, biotope_root),
            keywords=list(overrides.get("keywords") or []) or None,
            excludes=[
                SCAFFOLD_FILENAME,
                f"**/{SCAFFOLD_FILENAME}",
                ".biotope/**",
                "**/.biotope/**",
                ".git/**",
                "**/.git/**",
            ],
            rai_fields=overrides.get("rai_fields") or None,
        )
        report.attach(generator)

        try:
            metadata_dict = normalize_metadata_shape(generator.generate_metadata(progress_callback=report))
        except ValueError as exc:
            bake_error = exc
        report.finish(generator.scan_report.to_dict())

    if bake_error is not None:
        if str(bake_error) != "No supported files found in the dataset":
            report.result.update(status="failed", error=str(bake_error))
            reporter.row("FAIL", str(rel_dir), str(bake_error))
            return None
        metadata_dict = _build_minimal_directory_metadata(abs_dir, biotope_root, overrides, defaults)

    metadata_dict.setdefault("dateCreated", now)
    _apply_dataset_metadata(metadata_dict, defaults, overrides, biotope_root)
    _append_uncovered_file_objects(metadata_dict, abs_dir, biotope_root)
    _apply_pipeline_state(metadata_dict, overrides)

    write_text_atomic(output or target.metadata_path, json.dumps(metadata_dict, indent=2, default=str) + "\n")
    reporter.saved(output or target.metadata_path, metadata_dict)

    n_source_files = sum(1 for _ in _iter_directory_files(abs_dir))
    return metadata_dict, n_source_files


def _build_minimal_directory_metadata(
    abs_dir: Path,
    biotope_root: Path,
    overrides: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    """Build a minimal dataset for directories without baker-supported files."""
    relative_dir = abs_dir.relative_to(biotope_root)
    metadata = merge_metadata(
        {
            "name": overrides.get("name") or str(relative_dir),
            "description": (
                overrides.get("description") or defaults.get("description") or f"Dataset for {relative_dir}"
            ),
            "distribution": [],
        }
    )
    for file_path in _iter_directory_files(abs_dir):
        metadata["distribution"].append(make_file_object(file_path, biotope_root))
    return metadata


def _append_uncovered_file_objects(
    metadata_dict: dict[str, Any],
    abs_dir: Path,
    biotope_root: Path,
) -> None:
    """Append file pointers for physical files not covered by croissant-baker."""
    covered_files = _covered_files(metadata_dict, abs_dir, biotope_root)
    distributions = metadata_dict.setdefault("distribution", [])

    for file_path in _iter_directory_files(abs_dir):
        resolved = file_path.resolve()
        if resolved in covered_files:
            continue
        distributions.append(make_file_object(file_path, biotope_root))


def _covered_files(
    metadata_dict: dict[str, Any],
    abs_dir: Path,
    biotope_root: Path,
) -> set[Path]:
    """Resolve all physical files already covered by distribution entries."""
    covered: set[Path] = set()

    for distribution in metadata_dict.get("distribution", []) or []:
        entry_type = distribution.get("@type")
        if entry_type == FILE_OBJECT_TYPE:
            content_url = distribution.get("contentUrl")
            if not content_url:
                continue
            candidate = resolve_content_url(content_url, abs_dir, biotope_root)
            if candidate is not None and candidate.is_file():
                covered.add(candidate.resolve())
            continue

        if entry_type != "cr:FileSet":
            continue

        includes = distribution.get("includes")
        patterns = [includes] if isinstance(includes, str) else list(includes or [])
        for pattern in patterns:
            for candidate in abs_dir.glob(pattern):
                if candidate.is_file():
                    covered.add(candidate.resolve())

    return covered


def _iter_directory_files(abs_dir: Path):
    """Yield physical data files under a rooted directory, skipping biotope-owned paths."""
    for file_path in abs_dir.rglob("*"):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(abs_dir)
        if any(part.startswith(".") for part in relative.parts):
            continue
        yield file_path


def _default_overrides() -> dict[str, Any]:
    """Return the default add metadata overrides."""
    return {
        "name": None,
        "description": None,
        "license": None,
        "creator": None,
        "creator_email": None,
        "url": None,
        "citation": None,
        "version": None,
        "keywords": [],
        "access_restrictions": None,
        "legal_obligations": None,
        "collaboration_partner": None,
        "rai_fields": {},
        "status_override": None,
        "derived_from": [],
    }


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


def _resolve_dataset_ref(ref: str, biotope_root: Path) -> str:
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

    # Bare canonical id (no suffix); accept as-is if a manifest exists.
    candidate_manifest = datasets_dir / f"{ref}.jsonld"
    if candidate_manifest.is_file():
        return ref

    p = Path(ref)
    if not p.is_absolute():
        p = (biotope_root / p).resolve()
    else:
        p = p.resolve()

    # Path to a manifest under .biotope/datasets/.
    try:
        rel_manifest = p.relative_to(datasets_dir)
        if rel_manifest.suffix == ".jsonld" and p.is_file():
            return str(rel_manifest.with_suffix(""))
    except ValueError:
        pass

    # Path to a data file/dir inside the project — derive the canonical id.
    try:
        rel = p.relative_to(biotope_root)
    except ValueError as exc:
        msg = f"--derived-from {ref!r}: path is outside the biotope project"
        raise ValueError(msg) from exc

    file_manifest = (datasets_dir / rel).with_suffix(".jsonld")
    if file_manifest.is_file():
        return str(rel.with_suffix("") if rel.suffix else rel)

    # If it's a data dir we just baked, the canonical id is the dir rel path.
    dir_manifest = (datasets_dir / rel).with_suffix(".jsonld")
    if dir_manifest.is_file():
        return str(rel)

    msg = (
        f"--derived-from {ref!r}: no manifest found under .biotope/datasets/. "
        "Pass a dataset name (e.g. 'data/kidney_pdf'), a data path, or a "
        ".jsonld path of an existing dataset."
    )
    raise ValueError(msg)


def _generate_biotope_scaffold_from_baked(
    source_dir: Path,
    metadata_dict: dict[str, Any],
    biotope_root: Path,
    *,
    reporter: AddOutput | None = None,
) -> None:
    """Generate a scoped YAML scaffold for one directory-baked dataset."""
    scaffold_path = source_dir / SCAFFOLD_FILENAME

    dist_by_id = {
        distribution.get("@id"): distribution
        for distribution in metadata_dict.get("distribution", [])
        if distribution.get("@id")
    }

    creator_name = ""
    creator_email = ""
    creator_node = metadata_dict.get("creator")
    if isinstance(creator_node, dict):
        creator_name = creator_node.get("name", "") or ""
        creator_email = creator_node.get("email", "") or ""

    keywords = metadata_dict.get("keywords", [])
    if isinstance(keywords, list):
        keywords_value = [str(k) for k in keywords]
    elif keywords:
        keywords_value = [str(keywords)]
    else:
        keywords_value = []

    dataset_block = {
        "source_path": str(source_dir.relative_to(biotope_root)),
        "name": metadata_dict.get("name", "") or "",
        "description": metadata_dict.get("description", "") or "",
        "creator": creator_name,
        "creator_email": creator_email,
        "license": metadata_dict.get("license", "") or "",
        "url": metadata_dict.get("url", "") or "",
        "citation": metadata_dict.get("citation", "") or "",
        "version": metadata_dict.get("version", "") or "",
        "keywords": keywords_value,
        "access_restrictions": metadata_dict.get("cr:accessRestrictions", "") or "",
        "legal_obligations": metadata_dict.get("cr:legalObligations", "") or "",
        "collaboration_partner": metadata_dict.get("cr:collaborationPartner", "") or "",
    }

    record_set_blocks: list[dict[str, Any]] = []
    for record_set in metadata_dict.get("recordSet", []) or []:
        source_id = _first_field_source_id(record_set)
        distribution = dist_by_id.get(source_id, {})
        record_set_blocks.append(
            {
                "id": record_set.get("@id", "") or "",
                "source_path": _human_source_path(distribution, source_dir, biotope_root),
                "name": record_set.get("name", "") or "",
                "description": record_set.get("description", "") or "",
                "encoding_format": distribution.get("encodingFormat", "") or "",
            }
        )

    payload = {"dataset": dataset_block, "record_sets": record_set_blocks}
    header = (
        f"# {SCAFFOLD_FILENAME} — edit, then `biotope annotate apply {source_dir.relative_to(biotope_root)}`\n"
        "# Empty strings are placeholders; fill in or leave blank.\n"
        "# Schema: dataset (one block) + record_sets (list, joined by `id`).\n\n"
    )
    try:
        with open(scaffold_path, "w", encoding="utf-8") as handle:
            handle.write(header)
            yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)
        if reporter is not None:
            reporter.template(source_dir, scaffold_path)
    except Exception as exc:  # noqa: BLE001
        message = f"Could not generate {SCAFFOLD_FILENAME}: {exc}"
        if reporter is not None:
            reporter.warning(source_dir, message)
        else:
            click.echo(message, err=True)
        return

    stale_csv = source_dir / ".biotope.csv"
    if stale_csv.is_file():
        message = f"Old .biotope.csv found; use {SCAFFOLD_FILENAME} for annotations."
        if reporter is not None:
            reporter.warning(source_dir, message)
        else:
            click.echo(message, err=True)


def _human_source_path(distribution: dict[str, Any], source_dir: Path, biotope_root: Path) -> str:
    """Return a human-readable source path for one record set row."""
    entry_type = distribution.get("@type")
    if entry_type == FILE_OBJECT_TYPE:
        content_url = distribution.get("contentUrl", "") or ""
        candidate = resolve_content_url(content_url, source_dir, biotope_root)
        if candidate is not None:
            return str(candidate.relative_to(biotope_root))
        return content_url

    if entry_type == "cr:FileSet":
        includes = distribution.get("includes")
        pattern = includes if isinstance(includes, str) else (includes[0] if includes else "")
        if not pattern:
            return str(source_dir.relative_to(biotope_root))
        base = Path(pattern).parent
        source_path = source_dir / base if str(base) != "." else source_dir
        return str(source_path.relative_to(biotope_root))

    return str(source_dir.relative_to(biotope_root))


def _first_field_source_id(record_set: dict[str, Any]) -> str | None:
    """Return the @id of the FileSet/FileObject that the first field sources."""
    for field in record_set.get("field", []) or []:
        source = field.get("source") or {}
        for key in ("fileSet", "fileObject"):
            value = source.get(key)
            if isinstance(value, dict) and value.get("@id"):
                return value["@id"]
            if isinstance(value, str) and value:
                return value
    return None
