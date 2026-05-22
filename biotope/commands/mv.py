"""Move command implementation for tracking data files and updating metadata.

Three shapes of move land here:

1. **Whole-dataset rename/relocate.** Source is a directory that mirrors a
   manifest at ``.biotope/datasets/<rel>.jsonld``. We move the data dir,
   rename the manifest to mirror the new path, and rewrite the manifest's
   ``name`` + every ``contentUrl`` prefix. Nested sub-dataset manifests are
   carried with it. **Primary case** for the raw→processed dance.

2. **Single file inside a multi-file manifest.** Destination must stay
   under the manifest's dataset directory. We update the ``contentUrl`` in
   place and do **not** move the manifest — other files in it would be
   orphaned otherwise. ``cr:FileSet``-covered files are allowed only when
   the new name still matches the glob; cross-dataset moves are refused.

3. **Legacy single-file manifest.** The historical case: one
   ``cr:FileObject`` per ``.jsonld``. Manifest follows the data file.
"""

import fnmatch
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import click
from rich.console import Console
from rich.panel import Panel

from biotope.metadata import (
    FILE_OBJECT_TYPE,
    dataset_dir_for_manifest,
    ensure_no_legacy_file_objects,
    file_coverage_in_manifest,
)
from biotope.utils import (
    calculate_file_checksum,
    find_biotope_root,
    is_file_tracked,
    is_git_repo,
    stage_git_changes,
)


@click.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.argument("destination", type=click.Path(path_type=Path))
@click.option("--force", "-f", is_flag=True, help="Overwrite destination if it exists")
@click.option("--recursive", "-r", is_flag=True, help="Move directories recursively")
def mv(
    source: Path,
    destination: Path,
    force: bool,
    recursive: bool,
) -> None:
    """
    Move a tracked file or directory and update metadata.

    Moves a data file or directory that is tracked in biotope to a new location and updates
    all associated metadata files to reflect the new path. Directory structure
    will be created automatically if needed.

    Args:
        source: Path to the file or directory to move
        destination: Path to move the file or directory to
        force: Overwrite destination if it exists
        recursive: Move directories recursively
    """
    console = Console()

    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    if not is_git_repo(biotope_root):
        click.echo("❌ Not in a Git repository. Initialize Git first with 'git init .'")
        raise click.Abort

    # Resolve file paths to absolute paths if they're relative
    if not source.is_absolute():
        source = source.resolve()
    if not destination.is_absolute():
        destination = destination.resolve()

    # Handle directory vs file validation
    if source.is_dir():
        if not recursive:
            click.echo(f"❌ '{source}' is a directory. Use --recursive (-r) to move directories.")
            raise click.Abort

        # Check if directory contains any tracked files
        tracked_files = _find_tracked_files_in_directory(source, biotope_root)
        if not tracked_files:
            click.echo(f"❌ Directory '{source}' contains no tracked files.")
            raise click.Abort
    else:
        # Validate source file is tracked
        if not is_file_tracked(source, biotope_root):
            click.echo(f"❌ File '{source}' is not tracked. Use 'biotope add' first.")
            raise click.Abort

    # Validate move operation and get actual destination
    actual_destination = _validate_move_operation(source, destination, biotope_root, force)

    # Execute move
    if source.is_dir():
        _execute_directory_move(source, actual_destination, biotope_root, console)
    else:
        _execute_move(source, actual_destination, biotope_root, console)


def _resolve_destination_path(source: Path, destination: Path) -> Path:
    """Resolve the actual destination path following standard mv behavior."""
    # If destination is an existing directory, move into it with same filename
    if destination.exists() and destination.is_dir():
        return destination / source.name

    # Otherwise, use destination as-is (rename/move to exact path)
    return destination


def _load_metadata_file(metadata_file: Path) -> dict:
    """Load metadata and reject legacy file object types."""
    with open(metadata_file) as handle:
        metadata = json.load(handle)
    ensure_no_legacy_file_objects(metadata)
    return metadata


def _validate_move_operation(
    source: Path,
    destination: Path,
    biotope_root: Path,
    force: bool,
) -> Path:
    """Validate the move operation before executing and return the actual destination path."""
    # Adjust destination path like standard mv command
    actual_destination = _resolve_destination_path(source, destination)

    # Check if moving outside project
    try:
        actual_destination.relative_to(biotope_root)
    except ValueError:
        click.echo("❌ Cannot move file outside biotope project")
        raise click.Abort

    # Check if source and destination are the same
    if source.resolve() == actual_destination.resolve():
        click.echo("❌ Source and destination are the same")
        raise click.Abort

    # Check if moving biotope internal files
    try:
        source_rel = source.relative_to(biotope_root)
        if str(source_rel).startswith(".biotope/"):
            click.echo("❌ Cannot move biotope internal files")
            raise click.Abort
    except ValueError:
        pass  # Source is outside project, which is fine

    # Check destination conflicts
    if actual_destination.exists() and not force:
        click.echo(f"❌ Destination '{actual_destination}' exists. Use --force to overwrite.")
        raise click.Abort

    return actual_destination


def _execute_move(source: Path, destination: Path, biotope_root: Path, console: Console) -> None:
    """Execute the actual move operation."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    metadata_files = _find_metadata_files_for_file(source, biotope_root)

    if not metadata_files:
        click.echo("⚠️  No metadata files found referencing this file")
        return

    # If any owning manifest is multi-file, fork to the in-place update path.
    # The legacy "move manifest alongside" logic only fires when every owning
    # manifest is single-file (one FileObject, no FileSet) — i.e. the
    # historical 1-manifest-per-file shape.
    if any(_is_multi_file_manifest_at(m) for m in metadata_files):
        _execute_move_for_multifile(source, destination, biotope_root, metadata_files, console)
        return

    # Calculate source and destination relative paths for metadata file naming
    source_rel = source.relative_to(biotope_root)
    destination_rel = destination.relative_to(biotope_root)

    # Pre-validate that we can update all metadata files
    validation_results = []
    for metadata_file in metadata_files:
        # Test if we can read and update the metadata file
        try:
            metadata = _load_metadata_file(metadata_file)

            # Check if the file reference exists in this metadata
            has_reference = False
            for distribution in metadata.get("distribution", []):
                if distribution.get("@type") == FILE_OBJECT_TYPE and distribution.get("contentUrl") == str(source_rel):
                    has_reference = True
                    break

            if has_reference:
                # Test if we can write to the metadata file
                test_metadata = metadata.copy()
                for distribution in test_metadata.get("distribution", []):
                    if distribution.get("@type") == FILE_OBJECT_TYPE and distribution.get("contentUrl") == str(
                        source_rel
                    ):
                        distribution["contentUrl"] = str(destination_rel)
                        distribution["dateModified"] = datetime.now(timezone.utc).isoformat()
                        break

                # Test write by writing to a temporary file
                import tempfile

                with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=metadata_file.parent) as temp_file:
                    json.dump(test_metadata, temp_file, indent=2)
                    temp_file_path = Path(temp_file.name)

                # Clean up test file
                temp_file_path.unlink()
                validation_results.append((metadata_file, True))
            else:
                validation_results.append((metadata_file, False))

        except (json.JSONDecodeError, IOError, OSError) as e:
            validation_results.append((metadata_file, False, str(e)))

    # Check if all metadata files can be updated
    failed_validations = [r for r in validation_results if not r[1]]
    if failed_validations:
        console.print("[bold red]❌ Failed to validate metadata updates:[/]")
        for failed in failed_validations:
            if len(failed) > 2:
                console.print(f"  - {failed[0]}: {failed[2]}")
            else:
                console.print(f"  - {failed[0]}: Unknown error")
        raise click.Abort

    # Move the actual data file
    try:
        shutil.move(str(source), str(destination))
    except OSError as e:
        console.print(f"[bold red]❌ Failed to move file: {e}[/]")
        raise click.Abort

    # Calculate new checksum after move
    try:
        new_checksum = calculate_file_checksum(destination)
    except OSError as e:
        # Rollback: move file back
        try:
            shutil.move(str(destination), str(source))
        except OSError:
            console.print(f"[bold red]❌ Failed to rollback file move. File is at {destination}[/]")
        console.print(f"[bold red]❌ Failed to calculate checksum: {e}[/]")
        raise click.Abort

    updated_files = []
    moved_metadata_files = []
    rollback_needed = False

    try:
        for metadata_file in metadata_files:
            # Update the content of the metadata file
            if _update_metadata_file_path(
                metadata_file,
                str(source_rel),
                str(destination_rel),
                new_checksum,
                biotope_root,
            ):
                updated_files.append(metadata_file)

                # Calculate new metadata file path based on the data file's new location
                # Keep the original metadata file name to avoid conflicts
                new_metadata_path = biotope_root / ".biotope" / "datasets" / destination_rel.parent / metadata_file.name

                # Move the metadata file to mirror the new data file structure
                if new_metadata_path != metadata_file:
                    new_metadata_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.move(str(metadata_file), str(new_metadata_path))
                        moved_metadata_files.append((metadata_file, new_metadata_path))
                    except OSError as e:
                        console.print(f"[bold red]❌ Failed to move metadata file: {e}[/]")
                        rollback_needed = True
                        break

    except Exception as e:
        console.print(f"[bold red]❌ Failed to update metadata: {e}[/]")
        rollback_needed = True

    # Rollback if needed
    if rollback_needed:
        console.print("[bold yellow]🔄 Rolling back changes...[/]")

        # Rollback metadata file moves
        for old_path, new_path in reversed(moved_metadata_files):
            try:
                if new_path.exists():
                    shutil.move(str(new_path), str(old_path))
            except OSError as e:
                console.print(f"[bold red]❌ Failed to rollback metadata file move: {e}[/]")

        # Rollback data file move
        try:
            shutil.move(str(destination), str(source))
        except OSError:
            console.print(f"[bold red]❌ Failed to rollback file move. File is at {destination}[/]")

        raise click.Abort

    if updated_files or moved_metadata_files:
        stage_git_changes(biotope_root)

    console.print(
        Panel(
            f"[bold green]✅ Moved:[/] {source}\n"
            f"[bold green]To:[/] {destination}\n"
            f"[bold blue]📝 Updated {len(updated_files)} metadata file(s)[/]"
            + (
                f"\n[bold blue]📁 Moved {len(moved_metadata_files)} metadata file(s)[/]" if moved_metadata_files else ""
            ),
            title="Move Complete",
        )
    )

    console.print("\n💡 Next steps:")
    console.print("  1. Run 'biotope status' to see the changes")
    console.print("  2. Run 'biotope check-data' to verify file integrity")
    console.print("  3. Run 'biotope commit -m \"message\"' to save changes")


def _find_tracked_files_in_directory(directory: Path, biotope_root: Path) -> List[Path]:
    """Find all tracked files within a directory recursively."""
    tracked_files = []

    for file_path in directory.rglob("*"):
        if file_path.is_file() and is_file_tracked(file_path, biotope_root):
            tracked_files.append(file_path)

    return tracked_files


def _execute_directory_move(source: Path, destination: Path, biotope_root: Path, console: Console) -> None:
    """Execute move operation for a directory and all its tracked files."""
    # Whole-dataset rename/relocate: if the source dir mirrors a manifest at
    # `.biotope/datasets/<source_rel>.jsonld`, this is the primary case. Move
    # the data, rename the manifest, rewrite the manifest's `name` field and
    # every `contentUrl` prefix. Carry nested sub-dataset manifests along.
    source_rel = source.relative_to(biotope_root)
    top_manifest = biotope_root / ".biotope" / "datasets" / f"{source_rel}.jsonld"
    if top_manifest.is_file():
        _whole_dataset_rename(source, destination, biotope_root, console)
        return

    # Find all tracked files in the source directory
    tracked_files = _find_tracked_files_in_directory(source, biotope_root)

    if not tracked_files:
        click.echo("⚠️  No tracked files found in directory")
        return

    # Calculate relative paths
    source_rel = source.relative_to(biotope_root)
    destination_rel = destination.relative_to(biotope_root)

    # Determine metadata directories
    source_metadata_dir = biotope_root / ".biotope" / "datasets" / source_rel
    destination_metadata_dir = biotope_root / ".biotope" / "datasets" / destination_rel

    # Check if this is a simple directory rename (same parent directory)
    is_simple_rename = source.parent == destination.parent and source_metadata_dir.exists()

    # Pre-validate metadata updates
    validation_results = []

    if is_simple_rename and source_metadata_dir.exists():
        # Validate simple rename metadata updates
        for metadata_file in source_metadata_dir.rglob("*.jsonld"):
            try:
                metadata = _load_metadata_file(metadata_file)

                # Check if this metadata file needs updates
                needs_update = False
                for distribution in metadata.get("distribution", []):
                    if distribution.get("@type") == FILE_OBJECT_TYPE:
                        old_content_url = distribution.get("contentUrl")
                        if old_content_url and old_content_url.startswith(str(source_rel)):
                            needs_update = True
                            break

                if needs_update:
                    # Test write by writing to a temporary file
                    import tempfile

                    with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=metadata_file.parent) as temp_file:
                        json.dump(metadata, temp_file, indent=2)
                        temp_file_path = Path(temp_file.name)

                    # Clean up test file
                    temp_file_path.unlink()
                    validation_results.append((metadata_file, True))
                else:
                    validation_results.append((metadata_file, False))

            except (json.JSONDecodeError, IOError, OSError) as e:
                validation_results.append((metadata_file, False, str(e)))
    else:
        # Validate complex move metadata updates
        file_metadata_map = {}
        for file_path in tracked_files:
            metadata_files = _find_metadata_files_for_file(file_path, biotope_root)
            if metadata_files:
                file_metadata_map[file_path] = metadata_files

        for old_file_path, metadata_files in file_metadata_map.items():
            for metadata_file in metadata_files:
                try:
                    metadata = _load_metadata_file(metadata_file)

                    # Check if this metadata file needs updates
                    needs_update = False
                    old_rel_path = old_file_path.relative_to(biotope_root)
                    for distribution in metadata.get("distribution", []):
                        if distribution.get("@type") == FILE_OBJECT_TYPE and distribution.get("contentUrl") == str(
                            old_rel_path
                        ):
                            needs_update = True
                            break

                    if needs_update:
                        # Test write by writing to a temporary file
                        import tempfile

                        with tempfile.NamedTemporaryFile(mode="w", delete=False, dir=metadata_file.parent) as temp_file:
                            json.dump(metadata, temp_file, indent=2)
                            temp_file_path = Path(temp_file.name)

                        # Clean up test file
                        temp_file_path.unlink()
                        validation_results.append((metadata_file, True))
                    else:
                        validation_results.append((metadata_file, False))

                except (json.JSONDecodeError, IOError, OSError) as e:
                    validation_results.append((metadata_file, False, str(e)))

    # Check if all metadata files can be updated
    failed_validations = [r for r in validation_results if not r[1]]
    if failed_validations:
        console.print("[bold red]❌ Failed to validate metadata updates:[/]")
        for failed in failed_validations:
            if len(failed) > 2:
                console.print(f"  - {failed[0]}: {failed[2]}")
            else:
                console.print(f"  - {failed[0]}: Unknown error")
        raise click.Abort

    # Ensure destination directory exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Move the entire directory structure
    try:
        shutil.move(str(source), str(destination))
    except OSError as e:
        console.print(f"[bold red]❌ Failed to move directory: {e}[/]")
        raise click.Abort

    updated_files = []
    total_files_moved = len(tracked_files)
    rollback_needed = False

    try:
        if is_simple_rename and source_metadata_dir.exists():
            # For simple renames, rename the entire metadata directory structure
            destination_metadata_dir.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(source_metadata_dir), str(destination_metadata_dir))
            except OSError as e:
                console.print(f"[bold red]❌ Failed to move metadata directory: {e}[/]")
                rollback_needed = True

            if not rollback_needed:
                # Update all metadata files in the renamed directory
                for metadata_file in destination_metadata_dir.rglob("*.jsonld"):
                    # Read the metadata to find what file it references
                    try:
                        metadata = _load_metadata_file(metadata_file)

                        # Find file objects in the metadata
                        for distribution in metadata.get("distribution", []):
                            if distribution.get("@type") == FILE_OBJECT_TYPE:
                                old_content_url = distribution.get("contentUrl")
                                if old_content_url and old_content_url.startswith(str(source_rel)):
                                    # Update the path from source to destination
                                    new_content_url = old_content_url.replace(str(source_rel), str(destination_rel), 1)
                                    new_data_file = biotope_root / new_content_url

                                    if new_data_file.exists():
                                        new_checksum = calculate_file_checksum(new_data_file)
                                        if _update_metadata_file_path(
                                            metadata_file,
                                            old_content_url,
                                            new_content_url,
                                            new_checksum,
                                            biotope_root,
                                        ):
                                            updated_files.append(metadata_file)
                                            break  # Only update once per metadata file
                    except (json.JSONDecodeError, IOError, OSError) as e:
                        console.print(f"[bold red]❌ Failed to update metadata file {metadata_file}: {e}[/]")
                        rollback_needed = True
                        break
        else:
            # For moves to different locations, handle each tracked file individually
            file_metadata_map = {}
            for file_path in tracked_files:
                metadata_files = _find_metadata_files_for_file(file_path, biotope_root)
                if metadata_files:
                    file_metadata_map[file_path] = metadata_files

            moved_metadata_files = []

            # Update metadata for each tracked file that was moved
            for old_file_path, metadata_files in file_metadata_map.items():
                # Calculate the new file path
                relative_path = old_file_path.relative_to(source)
                new_file_path = destination / relative_path

                # Calculate new checksum for the moved file
                try:
                    new_checksum = calculate_file_checksum(new_file_path)
                except OSError as e:
                    console.print(f"[bold red]❌ Failed to calculate checksum for {new_file_path}: {e}[/]")
                    rollback_needed = True
                    break

                # Calculate relative paths for metadata updates
                old_rel_path = old_file_path.relative_to(biotope_root)
                new_rel_path = new_file_path.relative_to(biotope_root)

                for metadata_file in metadata_files:
                    # Update the content of the metadata file
                    if _update_metadata_file_path(
                        metadata_file,
                        str(old_rel_path),
                        str(new_rel_path),
                        new_checksum,
                        biotope_root,
                    ):
                        updated_files.append(metadata_file)

                        # Calculate new metadata file path based on the data file's new location
                        new_metadata_path = biotope_root / ".biotope" / "datasets" / new_rel_path.with_suffix(".jsonld")

                        # Move the metadata file to mirror the new data file structure
                        if new_metadata_path != metadata_file:
                            new_metadata_path.parent.mkdir(parents=True, exist_ok=True)
                            try:
                                shutil.move(str(metadata_file), str(new_metadata_path))
                                moved_metadata_files.append((metadata_file, new_metadata_path))
                            except OSError as e:
                                console.print(f"[bold red]❌ Failed to move metadata file: {e}[/]")
                                rollback_needed = True
                                break

                if rollback_needed:
                    break

            # Clean up empty directories in the old metadata location
            if not rollback_needed:
                _cleanup_empty_metadata_directories(source_metadata_dir, biotope_root)

    except Exception as e:
        console.print(f"[bold red]❌ Failed to update metadata: {e}[/]")
        rollback_needed = True

    # Rollback if needed
    if rollback_needed:
        console.print("[bold yellow]🔄 Rolling back changes...[/]")

        # Rollback directory move
        try:
            shutil.move(str(destination), str(source))
        except OSError:
            console.print(f"[bold red]❌ Failed to rollback directory move. Directory is at {destination}[/]")

        raise click.Abort

    if updated_files:
        stage_git_changes(biotope_root)

    console.print(
        Panel(
            f"[bold green]✅ Moved directory:[/] {source}\n"
            f"[bold green]To:[/] {destination}\n"
            f"[bold blue]📁 Moved {total_files_moved} tracked file(s)[/]\n"
            f"[bold blue]📝 Updated {len(updated_files)} metadata file(s)[/]",
            title="Directory Move Complete",
        )
    )

    console.print("\n💡 Next steps:")
    console.print("  1. Run 'biotope status' to see the changes")
    console.print("  2. Run 'biotope check-data' to verify file integrity")
    console.print("  3. Run 'biotope commit -m \"message\"' to save changes")


def _cleanup_empty_metadata_directories(metadata_dir: Path, biotope_root: Path) -> None:
    """Clean up empty metadata directories after moving files."""
    if not metadata_dir.exists():
        return

    datasets_root = biotope_root / ".biotope" / "datasets"
    current_dir = metadata_dir

    # Work our way up from the specific directory to the datasets root
    while current_dir != datasets_root and current_dir.exists():
        try:
            # Try to remove the directory if it's empty
            if current_dir.is_dir() and not any(current_dir.iterdir()):
                current_dir.rmdir()
                current_dir = current_dir.parent
            else:
                # If directory is not empty, stop cleanup
                break
        except OSError:
            # If we can't remove the directory, stop cleanup
            break


def _find_metadata_files_for_file(file_path: Path, biotope_root: Path) -> List[Path]:
    """Find every manifest that references a data file.

    Covers both the explicit ``cr:FileObject.contentUrl`` case and the
    multi-file ``cr:FileSet`` glob case. A file may legitimately appear in
    more than one manifest (e.g. nested datasets); all matches are returned.
    """
    metadata_files: List[Path] = []
    datasets_dir = biotope_root / ".biotope" / "datasets"
    if not datasets_dir.exists():
        return metadata_files

    for metadata_file in datasets_dir.rglob("*.jsonld"):
        try:
            metadata = _load_metadata_file(metadata_file)
        except (json.JSONDecodeError, OSError):
            continue
        dataset_dir = dataset_dir_for_manifest(metadata_file, biotope_root)
        coverage = file_coverage_in_manifest(metadata, dataset_dir, file_path, biotope_root)
        if coverage is not None:
            metadata_files.append(metadata_file)

    return metadata_files


def _whole_dataset_rename(source: Path, destination: Path, biotope_root: Path, console: Console) -> None:
    """Rename / relocate a whole dataset.

    Triggered when ``source`` is the data directory of a tracked dataset
    (a manifest exists at ``.biotope/datasets/<source_rel>.jsonld``). Moves
    the data, renames the top-level manifest, rewrites the manifest's
    ``name`` and every ``contentUrl`` prefix, and carries nested sub-dataset
    manifests along.

    FileSet ``includes`` patterns are relative to the dataset directory, so
    they need no rewriting.
    """
    source_rel = source.relative_to(biotope_root)
    destination_rel = destination.relative_to(biotope_root)
    datasets_dir = biotope_root / ".biotope" / "datasets"

    top_manifest = datasets_dir / f"{source_rel}.jsonld"
    new_top_manifest = datasets_dir / f"{destination_rel}.jsonld"

    if new_top_manifest.exists():
        console.print(
            f"[bold red]❌ Destination manifest already exists:[/] " f"{new_top_manifest.relative_to(biotope_root)}"
        )
        raise click.Abort

    # Collect every manifest to move: the top-level one, plus any nested
    # sub-dataset manifests under .biotope/datasets/<source_rel>/.
    nested_root = datasets_dir / source_rel
    nested_manifests = list(nested_root.rglob("*.jsonld")) if nested_root.is_dir() else []
    manifests_to_move = [(top_manifest, new_top_manifest)]
    for old in nested_manifests:
        rel_under_source = old.relative_to(nested_root)
        new = datasets_dir / destination_rel / rel_under_source
        manifests_to_move.append((old, new))

    # Move the data directory.
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(source), str(destination))
    except OSError as exc:
        console.print(f"[bold red]❌ Failed to move directory: {exc}[/]")
        raise click.Abort

    # Move + rewrite each manifest.
    rewritten: list[Path] = []
    old_prefix = str(source_rel)
    new_prefix = str(destination_rel)
    try:
        for old, new in manifests_to_move:
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(new))
            _rewrite_manifest_paths(new, old_prefix, new_prefix)
            rewritten.append(new)
    except Exception as exc:
        console.print(f"[bold red]❌ Failed during manifest rename: {exc}[/]")
        # Best-effort rollback of the data move; manifest moves up to this
        # point will be left in an intermediate state — the user can re-run.
        try:
            shutil.move(str(destination), str(source))
        except OSError:
            pass
        raise click.Abort

    # Prune empty parent directories left behind under .biotope/datasets/.
    if nested_root.is_dir():
        _prune_datasets_subtree(nested_root, datasets_dir)
    _prune_datasets_subtree(top_manifest.parent, datasets_dir)

    stage_git_changes(biotope_root)
    console.print(
        Panel(
            f"[bold green]✅ Renamed dataset[/]\n"
            f"   [cyan]{source_rel}[/cyan]  →  [cyan]{destination_rel}[/cyan]\n"
            f"[bold blue]📝 Rewrote {len(rewritten)} manifest(s) "
            f"(contentUrl prefixes + name fields)[/]",
            title="Dataset Rename Complete",
        )
    )


def _rewrite_manifest_paths(manifest_path: Path, old_prefix: str, new_prefix: str) -> None:
    """Rewrite every ``contentUrl`` and the ``name`` field whose value starts
    with the old dataset prefix. FileSet ``includes`` patterns are relative
    to the dataset dir and need no rewriting."""
    with open(manifest_path) as handle:
        metadata = json.load(handle)

    name = metadata.get("name")
    if isinstance(name, str) and (name == old_prefix or name.startswith(old_prefix + "/")):
        metadata["name"] = new_prefix + name[len(old_prefix) :]

    old_with_sep = old_prefix + "/"
    for distribution in metadata.get("distribution", []) or []:
        if distribution.get("@type") != FILE_OBJECT_TYPE:
            continue
        content_url = distribution.get("contentUrl")
        if not isinstance(content_url, str):
            continue
        if content_url == old_prefix:
            distribution["contentUrl"] = new_prefix
        elif content_url.startswith(old_with_sep):
            distribution["contentUrl"] = new_prefix + content_url[len(old_prefix) :]

    with open(manifest_path, "w") as handle:
        json.dump(metadata, handle, indent=2)


def _prune_datasets_subtree(start: Path, datasets_root: Path) -> None:
    """Remove empty directories from ``start`` upward, stopping at
    ``datasets_root``."""
    current = start
    while current != datasets_root and current.is_dir():
        try:
            if any(current.iterdir()):
                return
            current.rmdir()
        except OSError:
            return
        current = current.parent


def _is_multi_file_manifest_at(manifest_path: Path) -> bool:
    """A manifest is multi-file iff it covers more than one logical thing —
    multiple FileObjects, or any FileSet. The legacy `biotope add <file>`
    shape (one FileObject per `.jsonld`) returns False here."""
    try:
        with open(manifest_path) as handle:
            metadata = json.load(handle)
    except (OSError, ValueError):
        return False
    distribution = metadata.get("distribution", []) or []
    n_file_objects = sum(1 for d in distribution if d.get("@type") == FILE_OBJECT_TYPE)
    has_fileset = any(d.get("@type") == "cr:FileSet" for d in distribution)
    return n_file_objects > 1 or has_fileset


def _fileset_patterns(metadata: dict) -> list[str]:
    patterns: list[str] = []
    for distribution in metadata.get("distribution", []) or []:
        if distribution.get("@type") != "cr:FileSet":
            continue
        includes = distribution.get("includes")
        if isinstance(includes, str):
            patterns.append(includes)
        elif isinstance(includes, list):
            patterns.extend(p for p in includes if isinstance(p, str))
    return patterns


def _execute_move_for_multifile(
    source: Path,
    destination: Path,
    biotope_root: Path,
    metadata_files: List[Path],
    console: Console,
) -> None:
    """Move a single file that lives in a multi-file manifest.

    Constraint: destination must stay under the manifest's dataset directory
    — moving across dataset boundaries would orphan the manifest's
    `contentUrl` / `includes` claims about its own dataset dir.

    For each owning manifest:
      - FileObject coverage: update `contentUrl` in place. Don't move the
        manifest (other files depend on it).
      - FileSet coverage: rename succeeds iff the new path still matches the
        glob. Manifest stays untouched (the pattern still describes the new
        name). Otherwise refuse.
    """
    source_rel = source.relative_to(biotope_root)
    destination_rel = destination.relative_to(biotope_root)

    # Pre-validate every owning manifest before touching the filesystem.
    decisions: list[tuple[Path, str, dict]] = []  # (manifest_path, mode, metadata)
    for metadata_file in metadata_files:
        try:
            metadata = _load_metadata_file(metadata_file)
        except (json.JSONDecodeError, OSError) as exc:
            console.print(f"[bold red]❌ Cannot read {metadata_file}: {exc}[/]")
            raise click.Abort

        dataset_dir = dataset_dir_for_manifest(metadata_file, biotope_root)
        try:
            destination.relative_to(dataset_dir)
        except ValueError:
            console.print(
                f"[bold red]❌ Cross-dataset move refused.[/]\n"
                f"   {source_rel} is owned by [cyan]{metadata_file.relative_to(biotope_root)}[/cyan] "
                f"whose data lives under [cyan]{dataset_dir.relative_to(biotope_root)}/[/cyan].\n"
                f"   Destination [cyan]{destination_rel}[/cyan] is outside that directory.\n"
                f"   Use [bold]biotope add[/bold] at the new location and [bold]biotope rm[/bold] at the old."
            )
            raise click.Abort

        coverage = file_coverage_in_manifest(metadata, dataset_dir, source, biotope_root)
        if coverage == "file_object":
            decisions.append((metadata_file, "update_contentUrl", metadata))
            continue
        if coverage == "fileset":
            new_relative_to_dataset = str(destination.relative_to(dataset_dir))
            patterns = _fileset_patterns(metadata)
            if not any(fnmatch.fnmatch(new_relative_to_dataset, p) for p in patterns):
                console.print(
                    f"[bold red]❌ FileSet pattern would no longer cover the file after rename.[/]\n"
                    f"   {source_rel} is covered by a FileSet glob "
                    f"({', '.join(patterns)}) in "
                    f"[cyan]{metadata_file.relative_to(biotope_root)}[/cyan].\n"
                    f"   New path [cyan]{new_relative_to_dataset}[/cyan] doesn't match — "
                    f"either pick a name that does, or use rm + add."
                )
                raise click.Abort
            decisions.append((metadata_file, "fileset_no_op", metadata))
            continue
        # coverage None: discovered by _find_metadata_files_for_file but no
        # match here — skip without modifying anything.
        decisions.append((metadata_file, "skip", metadata))

    # Perform the data move.
    try:
        shutil.move(str(source), str(destination))
    except OSError as exc:
        console.print(f"[bold red]❌ Failed to move file: {exc}[/]")
        raise click.Abort

    try:
        new_checksum = calculate_file_checksum(destination)
    except OSError as exc:
        try:
            shutil.move(str(destination), str(source))
        except OSError:
            console.print(f"[bold red]❌ Failed to rollback file move. File is at {destination}[/]")
        console.print(f"[bold red]❌ Failed to calculate checksum: {exc}[/]")
        raise click.Abort

    updated: list[Path] = []
    fileset_passthroughs: list[Path] = []
    for metadata_file, mode, _ in decisions:
        if mode == "update_contentUrl":
            if _update_metadata_file_path(
                metadata_file,
                str(source_rel),
                str(destination_rel),
                new_checksum,
                biotope_root,
            ):
                updated.append(metadata_file)
        elif mode == "fileset_no_op":
            fileset_passthroughs.append(metadata_file)

    if updated or fileset_passthroughs:
        stage_git_changes(biotope_root)

    summary_lines = [
        f"[bold green]✅ Moved:[/] {source}",
        f"[bold green]To:[/] {destination}",
        f"[bold blue]📝 Updated contentUrl in {len(updated)} manifest(s) (in place)[/]",
    ]
    if fileset_passthroughs:
        summary_lines.append(
            f"[dim]ℹ {len(fileset_passthroughs)} FileSet glob(s) still match — no manifest change needed[/dim]"
        )
    console.print(Panel("\n".join(summary_lines), title="Move Complete"))
    console.print("\n💡 Next steps:")
    console.print("  1. Run 'biotope status' to see the changes")
    console.print("  2. Run 'biotope commit -m \"message\"' to save changes")


def _update_metadata_file_path(
    metadata_file: Path,
    old_path: str,
    new_path: str,
    new_checksum: str,
    biotope_root: Path,
) -> bool:
    """Update file path in a metadata file."""
    try:
        metadata = _load_metadata_file(metadata_file)

        updated = False
        for distribution in metadata.get("distribution", []):
            if distribution.get("@type") == FILE_OBJECT_TYPE and distribution.get("contentUrl") == old_path:
                distribution["contentUrl"] = new_path
                distribution["sha256"] = new_checksum
                distribution["dateModified"] = datetime.now(timezone.utc).isoformat()
                # Update file size
                new_file_path = biotope_root / new_path
                distribution["contentSize"] = new_file_path.stat().st_size
                updated = True

        if updated:
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

        return updated

    except (json.JSONDecodeError, IOError, OSError):
        return False
