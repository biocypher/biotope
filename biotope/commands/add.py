"""Add command implementation for tracking data files and metadata."""

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import click

from biotope.utils import (
    find_biotope_root,
    is_git_repo,
    stage_git_changes,
    calculate_file_checksum,
    load_project_metadata,
    is_file_tracked,
)


@click.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--recursive",
    "-r",
    is_flag=True,
    help="Add directories recursively",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force add even if file already tracked",
)
def add(paths: tuple[Path, ...], recursive: bool, force: bool) -> None:
    """Add data files to biotope project and stage for metadata creation.

    Single-file invocations produce one ``.jsonld`` per file under
    ``.biotope/datasets/``. Recursive directory invocations run
    croissant-baker over the rooted tree and produce ONE directory-level
    ``.jsonld``. Multi-part tables (e.g. partitioned parquet siblings)
    collapse into a single FileSet + RecordSet via baker's per-handler
    grouping, so the user chooses the dataset granularity by choosing
    where to point ``-r``.
    """
    if not paths:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        raise click.Abort

    # Find biotope project root
    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    # Check if we're in a Git repository
    if not is_git_repo(biotope_root):
        click.echo("❌ Not in a Git repository. Initialize Git first with 'git init'.")
        raise click.Abort

    datasets_dir = biotope_root / ".biotope" / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)

    added_entries: List[Path] = []
    skipped_entries: List[Path] = []
    baked_dirs: List[Tuple[Path, Path, dict]] = []

    for path in paths:
        if path.is_file():
            result = _add_file(path, biotope_root, datasets_dir, force)
            if result:
                added_entries.append(path)
            else:
                skipped_entries.append(path)
        elif path.is_dir() and recursive:
            baked = _bake_directory(path, biotope_root, datasets_dir)
            if baked is None:
                skipped_entries.append(path)
            else:
                jsonld_path, metadata_dict, n_source_files = baked
                added_entries.append(path)
                baked_dirs.append((path, jsonld_path, metadata_dict))
                n_record_sets = len(metadata_dict.get("recordSet", []))
                click.echo(
                    f"  ✨ Generated {jsonld_path.relative_to(biotope_root)} "
                    f"({n_source_files} source file(s), {n_record_sets} record set(s))"
                )
        elif path.is_dir():
            click.echo(
                f"⚠️  Skipping directory '{path}' (use --recursive to add contents)"
            )
            skipped_entries.append(path)

    if added_entries:
        stage_git_changes(biotope_root)

    for source_dir, jsonld_path, metadata_dict in baked_dirs:
        _generate_biotope_csv_from_baked(source_dir, metadata_dict, biotope_root)

    if added_entries:
        click.echo(f"\n✅ Added {len(added_entries)} entry(ies) to biotope project:")
        for entry in added_entries:
            click.echo(f"  + {entry}")

    if skipped_entries:
        click.echo(f"\n⚠️  Skipped {len(skipped_entries)} entry(ies):")
        for entry in skipped_entries:
            click.echo(f"  - {entry}")

    if added_entries:
        click.echo("\n💡 Next steps:")
        if baked_dirs:
            for source_dir, _jsonld_path, _md in baked_dirs:
                csv_path = source_dir / ".biotope.csv"
                click.echo(f"  • Edit annotations: {csv_path}")
                click.echo(f"    Then: biotope annotate batch --from-csv {csv_path}")
            click.echo("  • Finally: biotope commit -m \"message\"")
        else:
            click.echo("  1. Run 'biotope status' to see staged files")
            click.echo(
                "  2. Run 'biotope annotate interactive --staged' to create metadata"
            )
            click.echo("  3. Run 'biotope commit -m \"message\"' to save changes")

def _add_file(
    file_path: Path, biotope_root: Path, datasets_dir: Path, force: bool
) -> bool:
    """Add a single file to the biotope project."""

    # Resolve the file path to absolute path if it's relative
    if not file_path.is_absolute():
        file_path = file_path.resolve()

    # Calculate checksum
    sha256_hash = calculate_file_checksum(file_path)

    # Check if already tracked
    if not force and is_file_tracked(file_path, biotope_root):
        click.echo(f"⚠️  File {file_path.relative_to(biotope_root)} already tracked (use --force to override)")
        return False

    # Create basic metadata entry
    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": str(file_path.relative_to(biotope_root)),
        "description": f"Dataset for {file_path.name}",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": f"file_{sha256_hash[:8]}",
                "name": file_path.name,
                "contentUrl": str(file_path.relative_to(biotope_root)),
                "sha256": sha256_hash,
                "contentSize": file_path.stat().st_size,
                "dateCreated": datetime.now(tz=timezone.utc).isoformat(),
            }
        ],
    }

    metadata["dateCreated"] = datetime.now(tz=timezone.utc).isoformat()

    # Enrich with structural metadata from croissant-baker, if it can handle the file.
    _enrich_with_baker(metadata, file_path)

    # Top-level creator (from git, if available)
    git_name, git_email = _git_user_identity(biotope_root)
    if git_name:
        creator_obj = {"@type": "Person", "name": git_name}
        if git_email:
            creator_obj["email"] = git_email
        metadata["creator"] = creator_obj
    else:
        click.echo(
            "ℹ️  No Git identity found. Set it once to prefill 'creator' automatically:\n"
            "    git config --global user.name  \"Your Name\"\n"
            "    git config --global user.email \"you@example.com\""
        )

    # Inject project-level defaults for common metadata so later CSV import is a no-op
    try:
        project_defaults = load_project_metadata(biotope_root)
        for key in ("license", "citation", "cr:projectName"):
            value = project_defaults.get(key)
            if value and key not in metadata:
                metadata[key] = value
    except Exception:
        # If project metadata cannot be loaded, proceed without it
        pass

    # Save metadata to datasets directory with directory structure mirroring
    relative_path = file_path.relative_to(biotope_root)
    metadata_file = datasets_dir / relative_path.with_suffix(".jsonld")
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    return True

def _enrich_with_baker(metadata: dict, file_path: Path) -> None:
    """Attach baker-derived structural metadata under ``cr:recordSet`` if available.

    The shallow stub holds file-level info only. croissant-baker can extract
    column names, types, and row counts for handled formats (CSV, Parquet,
    JSON, FHIR, …). When a handler matches, store the extraction under
    ``cr:recordSet`` so downstream commands (``propose-mapping``, ``build``)
    can use it without rerunning baker.
    """
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

    record_set: dict = {
        "@type": "cr:RecordSet",
        "name": file_path.stem,
        "field": [],
    }
    column_types = extracted.get("column_types") or {}
    for col, ctype in column_types.items():
        record_set["field"].append(
            {
                "@type": "cr:Field",
                "name": col,
                "dataType": str(ctype),
            },
        )
    for stat_key in ("num_rows", "num_columns", "encoding_format"):
        if stat_key in extracted:
            record_set[f"cr:{stat_key}"] = extracted[stat_key]

    metadata.setdefault("recordSet", []).append(record_set)


def _git_user_identity(cwd: Path) -> tuple[str | None, str | None]:
    """Return (name, email) from `git config`, preferring repo-local config."""
    try:
        name = subprocess.run(
            ["git", "config", "--get", "user.name"],
            cwd=cwd,
            capture_output=True, text=True, check=False
        ).stdout.strip()
        email = subprocess.run(
            ["git", "config", "--get", "user.email"],
            cwd=cwd,
            capture_output=True, text=True, check=False
        ).stdout.strip()

        def _normalize(value: object) -> str | None:
            try:
                # Coerce to string and strip; ensure empty strings become None
                text = value if isinstance(value, str) else str(value)
                text = text.strip()
                return text or None
            except Exception:
                return None

        return _normalize(name), _normalize(email)
    except FileNotFoundError:
        return None, None


def _bake_directory(
    directory: Path, biotope_root: Path, datasets_dir: Path
) -> Optional[Tuple[Path, dict, int]]:
    """Run croissant-baker over ``directory``; write ONE directory-level jsonld.

    Baker's handlers group multi-file siblings (e.g. partitioned parquet)
    into a single FileSet + RecordSet, so the user chooses the dataset
    granularity by choosing where to root ``-r``. Returns
    ``(jsonld_path, metadata_dict, n_source_files)`` or ``None`` when
    baking fails or no supported files were found.
    """
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

    output_path = (datasets_dir / rel_dir).with_suffix(".jsonld")

    defaults = load_project_metadata(biotope_root)
    git_name, git_email = _git_user_identity(biotope_root)

    creators = None
    if git_name:
        creator: dict = {"name": git_name}
        if git_email:
            creator["email"] = git_email
        creators = [creator]
    elif isinstance(defaults.get("creator"), dict) and defaults["creator"].get("name"):
        creators = [{"name": defaults["creator"]["name"]}]

    generator = MetadataGenerator(
        dataset_path=str(abs_dir),
        name=str(rel_dir),
        description=defaults.get("description"),
        url=defaults.get("url"),
        license=defaults.get("license"),
        citation=defaults.get("citation"),
        creators=creators,
        # Skip baker's per-file .biotope.csv annotation templates — these
        # are biotope's own scaffolding, not part of the dataset.
        excludes=[".biotope.csv", "**/.biotope.csv"],
    )

    try:
        metadata_dict = generator.generate_metadata()
    except ValueError as exc:
        click.echo(f"⚠️  Could not bake {rel_dir}: {exc}")
        return None

    # Inject project-level Croissant-extension fields that mlcroissant
    # doesn't expose natively.
    for key in (
        "cr:projectName",
        "cr:accessRestrictions",
        "cr:legalObligations",
        "cr:collaborationPartner",
    ):
        if defaults.get(key):
            metadata_dict[key] = defaults[key]
    metadata_dict["dateCreated"] = datetime.now(tz=timezone.utc).isoformat()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metadata_dict, f, indent=2, default=str)

    n_source_files = 0
    for dist in metadata_dict.get("distribution", []):
        atype = dist.get("@type")
        if atype == "cr:FileObject":
            n_source_files += 1
        elif atype == "cr:FileSet":
            includes = dist.get("includes")
            patterns = (
                [includes]
                if isinstance(includes, str)
                else list(includes or [])
            )
            for pattern in patterns:
                n_source_files += sum(1 for p in abs_dir.glob(pattern) if p.is_file())

    return output_path, metadata_dict, n_source_files


def _generate_biotope_csv_from_baked(
    source_dir: Path, metadata_dict: dict, biotope_root: Path
) -> None:
    """Generate one CSV row per RecordSet in a directory-baked jsonld.

    The annotation unit is the logical table (a RecordSet), not the
    physical file. For partitioned tables this collapses many part-files
    into a single editable row — which is what users actually want to
    annotate.
    """
    csv_path = source_dir / ".biotope.csv"

    csv_columns = [
        "filepath",
        "record_set",
        "name",
        "description",
        "data_url",
        "creator",
        "project_name",
        "date_created",
        "access_restrictions",
        "encoding_format",
        "legal_obligations",
        "collaboration_partner",
        "publication_date",
        "version",
        "license_url",
        "citation",
    ]

    dist_by_id = {
        d.get("@id"): d for d in metadata_dict.get("distribution", []) if d.get("@id")
    }

    top_creator = ""
    creator_node = metadata_dict.get("creator")
    if isinstance(creator_node, dict):
        top_creator = creator_node.get("name", "") or ""
    elif isinstance(creator_node, list) and creator_node:
        first = creator_node[0]
        if isinstance(first, dict):
            top_creator = first.get("name", "") or ""

    top_url = metadata_dict.get("url", "") or ""
    top_license = metadata_dict.get("license", "") or ""
    top_citation = metadata_dict.get("citation", "") or ""
    top_version = metadata_dict.get("version", "") or ""
    top_date_published = metadata_dict.get("datePublished", "") or ""
    top_date_created = (metadata_dict.get("dateCreated", "") or "")[:10]
    top_project_name = metadata_dict.get("cr:projectName", "") or ""
    top_access = metadata_dict.get("cr:accessRestrictions", "") or ""
    top_legal = metadata_dict.get("cr:legalObligations", "") or ""
    top_collab = metadata_dict.get("cr:collaborationPartner", "") or ""

    try:
        rel_dir = source_dir.resolve().relative_to(biotope_root)
    except ValueError:
        rel_dir = Path(source_dir.name)

    rows = []
    for rs in metadata_dict.get("recordSet", []):
        source_id = _first_field_source_id(rs)
        dist = dist_by_id.get(source_id, {})
        atype = dist.get("@type")

        if atype == "cr:FileObject":
            filepath = dist.get("contentUrl", "") or ""
        elif atype == "cr:FileSet":
            includes = dist.get("includes")
            pattern = (
                includes
                if isinstance(includes, str)
                else (includes[0] if includes else "")
            )
            base = str(Path(pattern).parent) if pattern else ""
            filepath = (
                str(rel_dir / base) if base and base != "." else str(rel_dir)
            )
        else:
            filepath = str(rel_dir)

        rows.append(
            {
                "filepath": filepath,
                "record_set": rs.get("@id", "") or "",
                "name": rs.get("name", "") or "",
                "description": rs.get("description", "") or "",
                "data_url": top_url,
                "creator": top_creator,
                "project_name": top_project_name,
                "date_created": top_date_created,
                "access_restrictions": top_access,
                "encoding_format": dist.get("encodingFormat", "") or "",
                "legal_obligations": top_legal,
                "collaboration_partner": top_collab,
                "publication_date": top_date_published,
                "version": top_version,
                "license_url": top_license,
                "citation": top_citation,
            }
        )

    if not rows:
        click.echo("ℹ️  No record sets discovered, skipping CSV generation")
        return

    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_columns)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        click.echo(f"\n📝 Generated annotation template: {csv_path}")
    except Exception as e:
        click.echo(f"⚠️  Warning: Could not generate .biotope.csv: {e}")


def _first_field_source_id(record_set: dict) -> Optional[str]:
    """Return the @id of the FileSet/FileObject that the first field sources."""
    for field in record_set.get("field", []) or []:
        source = field.get("source") or {}
        for key in ("fileSet", "fileObject"):
            val = source.get(key)
            if isinstance(val, dict) and val.get("@id"):
                return val["@id"]
            if isinstance(val, str) and val:
                return val
    return None
