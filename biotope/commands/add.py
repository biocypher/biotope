"""Add command implementation for tracking data files and metadata."""

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

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
    """Add data files to biotope project and stage for metadata creation."""
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

    added_files = []
    skipped_files = []

    for path in paths:
        if path.is_file():
            result = _add_file(path, biotope_root, datasets_dir, force)
            if result:
                added_files.append(path)
            else:
                skipped_files.append(path)
        elif path.is_dir() and recursive:
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    result = _add_file(file_path, biotope_root, datasets_dir, force)
                    if result:
                        added_files.append(file_path)
                    else:
                        skipped_files.append(file_path)
        elif path.is_dir():
            click.echo(
                f"⚠️  Skipping directory '{path}' (use --recursive to add contents)"
            )
            skipped_files.append(path)

    # Stage changes in Git
    if added_files:
        stage_git_changes(biotope_root)

    # Generate .biotope.csv if appropriate
    if _should_generate_csv(paths, recursive, added_files):
        target_directory = paths[0]  # We know there's exactly one directory
        _generate_biotope_csv(target_directory, added_files, biotope_root)

    # Report results
    if added_files:
        click.echo(f"\n✅ Added {len(added_files)} file(s) to biotope project:")
        for file_path in added_files:
            click.echo(f"  + {file_path}")

    if skipped_files:
        click.echo(f"\n⚠️  Skipped {len(skipped_files)} file(s):")
        for file_path in skipped_files:
            click.echo(f"  - {file_path}")

    if added_files:
        click.echo(f"\n💡 Next steps:")
        
        # Check if we generated a CSV file and adjust instructions
        if _should_generate_csv(paths, recursive, added_files):
            target_directory = paths[0]
            csv_path = target_directory / ".biotope.csv"
            click.echo(f"  1. Edit the generated CSV file: {csv_path}")
            click.echo(f"  2. Run 'biotope annotate batch --from-csv {csv_path}' to apply annotations")
            click.echo(f"  3. Run 'biotope commit -m \"message\"' to save changes")
        else:
            click.echo(f"  1. Run 'biotope status' to see staged files")
            click.echo(
                f"  2. Run 'biotope annotate interactive --staged' to create metadata"
            )
            click.echo(f"  3. Run 'biotope commit -m \"message\"' to save changes")

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


def _generate_biotope_csv(directory: Path, added_files: List[Path], biotope_root: Path) -> None:
    """
    Generate a .biotope.csv file with pre-filled metadata from added files.
    
    Args:
        directory: The directory where files were added from
        added_files: List of files that were added to biotope
        biotope_root: Root of the biotope project
    """
    datasets_dir = biotope_root / ".biotope" / "datasets"
    csv_path = directory / ".biotope.csv"
    
    # Define all possible CSV columns with their descriptions
    csv_columns = [
        "filepath",  # Required
        "name",  # Can be derived from filepath
        "description",  # Required
        "data_url",  # Optional - URL to data source
        "creator",  # Optional - Contact person/creator
        "project_name",  # Optional
        "date_created",  # Can be derived from jsonld
        "access_restrictions",  # Optional
        "encoding_format",  # Optional - file format
        "legal_obligations",  # Optional
        "collaboration_partner",  # Optional
        "publication_date",  # Optional
        "version",  # Optional
        "license_url",  # Optional
        "citation",  # Optional
    ]
    
    csv_rows = []
    
    # Filter added files to only those in the target directory
    # added_files contains relative paths, directory is also relative
    directory_str = str(directory)
    directory_files = []
    for f in added_files:
        file_str = str(f)
        # Check if the file is within the target directory
        if file_str.startswith(directory_str + "/") or file_str == directory_str:
            directory_files.append(f)
    
    for file_path in directory_files:
        # Load existing metadata if available
        # file_path is relative to current working directory, convert to absolute then relative to biotope_root
        try:
            # file_path is relative, so resolve it first
            abs_file_path = (Path.cwd() / file_path).resolve()
            relative_path = abs_file_path.relative_to(biotope_root)
        except ValueError:
            # If file_path is not under biotope_root, skip it
            continue
        metadata_file = datasets_dir / relative_path.with_suffix(".jsonld")
        
        metadata = {}
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            except Exception:
                pass  # Use empty metadata if can't load
        
        # Extract information from metadata
        row = {}
        
        # Filepath (relative to biotope root)
        row["filepath"] = str(relative_path)
        
        # Name (from metadata or derive from filename)
        row["name"] = metadata.get("name", file_path.stem)
        
        # Description (from metadata or default)
        row["description"] = metadata.get("description", f"Dataset for {file_path.name}")
        
        # Extract date from distribution if available
        distribution = metadata.get("distribution", [])
        if distribution and isinstance(distribution, list) and len(distribution) > 0:
            date_created = distribution[0].get("dateCreated", "")
            if date_created:
                # Convert from ISO format to date only
                try:
                    parsed_date = datetime.fromisoformat(date_created.replace('Z', '+00:00'))
                    row["date_created"] = parsed_date.strftime("%Y-%m-%d")
                except Exception:
                    row["date_created"] = ""
            else:
                row["date_created"] = ""
        else:
            row["date_created"] = ""
        
        # Extract creator information if available
        creator = metadata.get("creator", {})
        if isinstance(creator, dict):
            row["creator"] = creator.get("name", "")
        else:
            row["creator"] = ""
        
        if not row.get("date_created"):
            row["date_created"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if not row.get("creator"):
            git_name, _git_email = _git_user_identity(biotope_root)
            if git_name:
                row["creator"] = git_name
        
        # Extract other metadata fields
        row["data_url"] = metadata.get("url", "")
        row["project_name"] = ""  # This would come from project metadata
        row["access_restrictions"] = metadata.get("cr:accessRestrictions", "")
        row["encoding_format"] = metadata.get("encodingFormat", "")
        row["legal_obligations"] = metadata.get("cr:legalObligations", "")
        row["collaboration_partner"] = metadata.get("cr:collaborationPartner", "")
        row["publication_date"] = metadata.get("datePublished", "")
        row["version"] = metadata.get("version", "")
        row["license_url"] = metadata.get("license", "")
        row["citation"] = metadata.get("citation", "")
        
        csv_rows.append(row)
    
    # Write CSV file if we have files to process
    if csv_rows:
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=csv_columns)
                
                # Write header
                writer.writeheader()
                
                # Write data rows
                for row in csv_rows:
                    writer.writerow(row)
            
            click.echo(f"\n📝 Generated annotation template: {csv_path}")
            click.echo("💡 Edit this file to add metadata, then run:")
            click.echo(f"   biotope annotate batch --from-csv {csv_path}")
            
        except Exception as e:
            click.echo(f"⚠️  Warning: Could not generate .biotope.csv: {e}")
    else:
        click.echo("ℹ️  No files added from this directory, skipping CSV generation")


def _should_generate_csv(paths: tuple[Path, ...], recursive: bool, added_files: List[Path]) -> bool:
    """
    Determine if we should generate a .biotope.csv file.
    
    Returns True if:
    - Recursive flag is used
    - Only one directory was specified as input
    - Files were actually added from that directory
    """
    if not recursive or not added_files:
        return False
    
    # Check if exactly one directory was specified
    if len(paths) == 1 and paths[0].is_dir():
        # Check if all added files are from this directory or its subdirectories
        target_dir = paths[0]  # Use relative path, not resolved
        for file_path in added_files:
            # Check if the file is within the target directory
            # file_path should be relative to current working directory
            file_path_str = str(file_path)
            target_dir_str = str(target_dir)
            if not (file_path_str.startswith(target_dir_str + "/") or file_path_str == target_dir_str):
                return False  # File is not within the target directory
        return True
    
    return False
