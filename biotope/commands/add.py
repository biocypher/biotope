"""Add command implementation for tracking data files and metadata."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import yaml

from biotope.metadata import (
    FILE_OBJECT_TYPE,
    SCAFFOLD_FILENAME,
    make_file_object,
    merge_metadata,
    normalize_metadata_shape,
    parse_key_value_pairs,
    resolve_target,
)
from biotope.utils import (
    find_biotope_root,
    is_git_repo,
    is_file_tracked,
    load_project_metadata,
    stage_git_changes,
)


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--force", "-f", is_flag=True, help="Force add even if file already tracked")
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
def add(
    paths: tuple[Path, ...],
    force: bool,
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
) -> None:
    """Add data files or rooted directories to a biotope project."""
    if not paths:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        raise click.Abort

    if name and len(paths) != 1:
        raise click.BadParameter("--name can only be used when adding one path.")

    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    if not is_git_repo(biotope_root):
        click.echo("❌ Not in a Git repository. Initialize Git first with 'git init'.")
        raise click.Abort

    try:
        rai_fields = parse_key_value_pairs(rai_pairs, "--rai")
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
    }

    datasets_dir = biotope_root / ".biotope" / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)

    added_entries: list[Path] = []
    skipped_entries: list[Path] = []
    baked_dirs: list[tuple[Path, dict[str, Any]]] = []

    for path in paths:
        if path.is_file():
            result = _add_file(path, biotope_root, datasets_dir, force, overrides)
            if result:
                added_entries.append(path)
            else:
                skipped_entries.append(path)
            continue

        baked = _bake_directory(path, biotope_root, overrides)
        if baked is None:
            skipped_entries.append(path)
            continue

        metadata_dict, n_source_files = baked
        added_entries.append(path)
        baked_dirs.append((path.resolve(), metadata_dict))
        n_record_sets = len(metadata_dict.get("recordSet", []))
        target = resolve_target(path, biotope_root)
        click.echo(
            f"  ✨ Generated {target.metadata_path.relative_to(biotope_root)} "
            f"({n_source_files} source file(s), {n_record_sets} record set(s))"
        )

    if added_entries:
        stage_git_changes(biotope_root)

    for source_dir, metadata_dict in baked_dirs:
        _generate_biotope_scaffold_from_baked(source_dir, metadata_dict, biotope_root)

    if added_entries:
        click.echo(f"\n✅ Added {len(added_entries)} entr(y/ies) to biotope project:")
        for entry in added_entries:
            click.echo(f"  + {entry}")

    if skipped_entries:
        click.echo(f"\n⚠️  Skipped {len(skipped_entries)} entr(y/ies):")
        for entry in skipped_entries:
            click.echo(f"  - {entry}")

    if added_entries:
        click.echo("\n💡 Next steps:")
        if baked_dirs:
            for source_dir, _metadata_dict in baked_dirs:
                click.echo(f"  • Review {source_dir / SCAFFOLD_FILENAME}")
                click.echo(f"    Then: biotope annotate apply {source_dir}")
            click.echo("  • Map data into the knowledge graph: biotope map")
            click.echo("  • Finally: biotope commit -m \"message\"")
        else:
            click.echo("  1. Run 'biotope status' to see staged files")
            click.echo("  2. Run 'biotope annotate edit --staged' to refine metadata")
            click.echo("  3. Run 'biotope commit -m \"message\"' to save changes")


def _add_file(
    file_path: Path,
    biotope_root: Path,
    datasets_dir: Path,
    force: bool,
    overrides: dict[str, Any] | None = None,
) -> bool:
    """Add a single file to the biotope project."""
    overrides = overrides or _default_overrides()
    abs_file = file_path.resolve()
    try:
        relative_path = abs_file.relative_to(biotope_root)
    except ValueError:
        click.echo(f"❌ File '{file_path}' is outside the biotope project.")
        return False

    if not force and is_file_tracked(abs_file, biotope_root):
        click.echo(
            f"⚠️  File {relative_path} already tracked (use --force to override)"
        )
        return False

    defaults = load_project_metadata(biotope_root)
    now = datetime.now(tz=timezone.utc).isoformat()
    metadata = merge_metadata(
        {
            "name": overrides.get("name") or str(relative_path),
            "description": (
                overrides.get("description")
                or defaults.get("description")
                or f"Dataset for {abs_file.name}"
            ),
            "distribution": [make_file_object(abs_file, biotope_root)],
            "dateCreated": now,
        }
    )

    _enrich_with_baker(metadata, abs_file)
    _apply_dataset_metadata(metadata, defaults, overrides, biotope_root)

    target = resolve_target(abs_file, biotope_root)
    target.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target.metadata_path, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    return True


def _enrich_with_baker(metadata: dict[str, Any], file_path: Path) -> None:
    """Attach baker-derived structural metadata under ``recordSet`` if available."""
    try:
        from croissant_baker.metadata_generator import find_handler, register_all_handlers
    except ImportError:
        return

    register_all_handlers()
    handler = find_handler(file_path)
    if handler is None:
        return

    try:
        extracted = handler.extract_metadata(file_path)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"⚠️  baker could not extract from {file_path.name}: {exc}")
        return

    record_set: dict[str, Any] = {
        "@type": "cr:RecordSet",
        "name": file_path.stem,
        "field": [],
    }
    column_types = extracted.get("column_types") or {}
    file_object_id = metadata["distribution"][0]["@id"]
    for column_name, column_type in column_types.items():
        record_set["field"].append(
            {
                "@type": "cr:Field",
                "name": column_name,
                "dataType": str(column_type),
                "source": {
                    "fileObject": {"@id": file_object_id},
                    "extract": {"column": column_name},
                },
            }
        )
    for stat_key in ("num_rows", "num_columns"):
        if stat_key in extracted:
            record_set[f"cr:{stat_key}"] = extracted[stat_key]

    metadata.setdefault("recordSet", []).append(record_set)


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
    default_name = (
        default_creator.get("name")
        if isinstance(default_creator, dict)
        else None
    )

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
    return [
        {
            key: value
            for key, value in creator_node.items()
            if key in {"name", "email", "url"}
        }
    ]


def _bake_directory(
    directory: Path,
    biotope_root: Path,
    overrides: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int] | None:
    """Run croissant-baker over ``directory`` and write one directory-level JSON-LD."""
    overrides = overrides or _default_overrides()
    try:
        from croissant_baker.metadata_generator import MetadataGenerator
    except ImportError:
        click.echo(
            "❌ croissant-baker is not installed. Install with `uv pip install croissant-baker`."
        )
        return None

    abs_dir = directory.resolve()
    try:
        rel_dir = abs_dir.relative_to(biotope_root)
    except ValueError:
        click.echo(f"❌ Directory '{directory}' is outside the biotope project.")
        return None

    target = resolve_target(abs_dir, biotope_root)
    defaults = load_project_metadata(biotope_root)
    now = datetime.now(tz=timezone.utc).isoformat()

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

    try:
        metadata_dict = normalize_metadata_shape(generator.generate_metadata())
    except ValueError as exc:
        if str(exc) != "No supported files found in the dataset":
            click.echo(f"⚠️  Could not bake {rel_dir}: {exc}")
            return None
        metadata_dict = _build_minimal_directory_metadata(abs_dir, biotope_root, overrides, defaults)

    metadata_dict.setdefault("dateCreated", now)
    _apply_dataset_metadata(metadata_dict, defaults, overrides, biotope_root)
    _dedupe_file_objects_covered_by_filesets(metadata_dict, abs_dir, biotope_root)
    _append_uncovered_file_objects(metadata_dict, abs_dir, biotope_root)

    target.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target.metadata_path, "w", encoding="utf-8") as handle:
        json.dump(metadata_dict, handle, indent=2, default=str)

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
                overrides.get("description")
                or defaults.get("description")
                or f"Dataset for {relative_dir}"
            ),
            "distribution": [],
        }
    )
    for file_path in _iter_directory_files(abs_dir):
        metadata["distribution"].append(make_file_object(file_path, biotope_root))
    return metadata


def _dedupe_file_objects_covered_by_filesets(
    metadata_dict: dict[str, Any],
    abs_dir: Path,
    biotope_root: Path,
) -> None:
    """Drop baker FileObjects whose contentUrl is already covered by a FileSet glob.

    Baker emits both a FileSet (with `includes` glob) and a FileObject per
    physical file. RecordSet field sources only reference the FileSet, so the
    per-file FileObjects are redundant. Keep FileObjects only when they are
    genuinely standalone (not glob-covered).
    """
    distributions = metadata_dict.get("distribution", []) or []
    fileset_covered: set[Path] = set()
    for distribution in distributions:
        if distribution.get("@type") != "cr:FileSet":
            continue
        includes = distribution.get("includes")
        patterns = [includes] if isinstance(includes, str) else list(includes or [])
        for pattern in patterns:
            for candidate in abs_dir.glob(pattern):
                if candidate.is_file():
                    fileset_covered.add(candidate.resolve())

    if not fileset_covered:
        return

    deduped: list[dict[str, Any]] = []
    for distribution in distributions:
        if distribution.get("@type") != FILE_OBJECT_TYPE:
            deduped.append(distribution)
            continue
        content_url = distribution.get("contentUrl")
        if not content_url:
            deduped.append(distribution)
            continue
        resolved = _resolve_distribution_path(content_url, abs_dir, biotope_root)
        if resolved is not None and resolved.resolve() in fileset_covered:
            continue
        deduped.append(distribution)

    metadata_dict["distribution"] = deduped


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
            candidate = _resolve_distribution_path(content_url, abs_dir, biotope_root)
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


def _resolve_distribution_path(
    content_url: str,
    abs_dir: Path,
    biotope_root: Path,
) -> Path | None:
    """Resolve a contentUrl against dataset-first, then project-root semantics."""
    dataset_candidate = abs_dir / content_url
    if dataset_candidate.exists():
        return dataset_candidate
    root_candidate = biotope_root / content_url
    if root_candidate.exists():
        return root_candidate
    return None


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
    }


def _generate_biotope_scaffold_from_baked(
    source_dir: Path,
    metadata_dict: dict[str, Any],
    biotope_root: Path,
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
        click.echo(f"\n📝 Generated annotation template: {scaffold_path}")
    except Exception as exc:  # noqa: BLE001
        click.echo(f"⚠️  Warning: Could not generate {SCAFFOLD_FILENAME}: {exc}")
        return

    stale_csv = source_dir / ".biotope.csv"
    if stale_csv.is_file():
        click.echo(
            f"⚠️  Found stale {stale_csv} from a previous biotope version. "
            f"The scaffold is now {SCAFFOLD_FILENAME}; you can safely delete the CSV.",
        )


def _human_source_path(distribution: dict[str, Any], source_dir: Path, biotope_root: Path) -> str:
    """Return a human-readable source path for one record set row."""
    entry_type = distribution.get("@type")
    if entry_type == FILE_OBJECT_TYPE:
        content_url = distribution.get("contentUrl", "") or ""
        candidate = _resolve_distribution_path(content_url, source_dir, biotope_root)
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
