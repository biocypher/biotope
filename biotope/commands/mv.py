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

import copy
import fnmatch
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import click
from rich.console import Console
from rich.panel import Panel

from biotope.croissant import annotation
from biotope.croissant.ids import MOVED_FROM, moved_ids, rename, renamer
from biotope.extraction.run import STATES
from biotope.graph.moves import follow_manifest, package_files, planned_ids, write_ids
from biotope.graph.sources import description_text, write_description, write_module, write_text_atomic
from biotope.graph.targets import Target
from biotope.metadata import (
    FILE_OBJECT_TYPE,
    dataset_dir_for_manifest,
    ensure_no_legacy_file_objects,
    file_coverage_in_manifest,
    manifest_for,
)
from biotope.utils import (
    calculate_file_checksum,
    find_biotope_root,
    is_file_tracked,
    warn_ignored,
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
        _move_extraction_state(source, actual_destination, biotope_root)


def _move_annotation(source: Path, destination: Path, biotope_root: Path) -> None:
    old, new = annotation.annotation_path(source), annotation.annotation_path(destination)
    if old.is_file():
        shutil.move(str(old), str(new))
        warn_ignored(biotope_root, [new])


def _move_extraction_state(source: Path, destination: Path, biotope_root: Path) -> None:
    old, new = (
        biotope_root / STATES / path.relative_to(biotope_root).with_suffix(".json") for path in (source, destination)
    )
    if old.is_file() and destination.is_file() and not source.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(new))
        warn_ignored(biotope_root, [new])


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
    plans = _planned(metadata_files, [(source, destination)], biotope_root)
    _apply(source, destination, plans, biotope_root, console)
    console.print(
        Panel(
            f"[bold green]✅ Moved:[/] {source}\n"
            f"[bold green]To:[/] {destination}\n"
            f"[bold blue]📝 Updated {len(plans)} metadata file(s)[/]",
            title="Move Complete",
        )
    )
    console.print("\n💡 Next steps:")
    console.print("  1. Run 'biotope status' to see the changes")
    console.print("  2. Run 'biotope check-data' to verify file integrity")


@dataclass
class _Plan:
    manifest: Path
    target: Path
    text: str
    annotation: Path | None
    annotation_text: str | None
    schemas: dict[Path, str]
    revised: list[Target]


def _planned(manifests: List[Path], moves: list[tuple[Path, Path]], biotope_root: Path) -> list[_Plan]:
    plans: list[_Plan] = []
    for manifest in manifests:
        try:
            refusal = _refusal(manifest, moves, biotope_root)
            plan = None if refusal else _plan(manifest, moves, biotope_root)
        except (OSError, ValueError) as exc:
            refusal = f"❌ Cannot update {manifest.relative_to(biotope_root)}: {exc}"
        if refusal:
            click.echo(refusal)
            raise click.Abort
        plans += [plan] if plan is not None else []
    return plans


def _refusal(manifest: Path, moves: list[tuple[Path, Path]], biotope_root: Path) -> str | None:
    if any(manifest == manifest_for(old, biotope_root) for old, _ in moves):
        return None
    metadata = _load_metadata_file(manifest)
    dataset_dir = dataset_dir_for_manifest(manifest, biotope_root)
    for old, new in moves:
        coverage = file_coverage_in_manifest(metadata, dataset_dir, old, biotope_root)
        if coverage is not None and not new.is_relative_to(dataset_dir):
            return (
                f"❌ Cross-dataset move refused. {old.relative_to(biotope_root)} is owned by "
                f"{manifest.relative_to(biotope_root)}, whose data lives under "
                f"{dataset_dir.relative_to(biotope_root)}/; {new.relative_to(biotope_root)} is outside it. "
                "Use biotope add at the new location and biotope rm at the old."
            )
        patterns = _fileset_patterns(metadata)
        if coverage == "fileset" and not any(
            fnmatch.fnmatch(new.relative_to(dataset_dir).as_posix(), pattern) for pattern in patterns
        ):
            return (
                f"❌ FileSet pattern would no longer cover the file after rename. {old.relative_to(biotope_root)} is "
                f"covered by a FileSet glob ({', '.join(patterns)}) in {manifest.relative_to(biotope_root)}; "
                f"{new.relative_to(dataset_dir).as_posix()} does not match it. "
                "Pick a name that does, or use rm and add."
            )
    return None


def _plan(
    manifest: Path, moves: list[tuple[Path, Path]], biotope_root: Path, checksum: str | None = None
) -> _Plan | None:
    metadata = _load_metadata_file(manifest)
    before = copy.deepcopy(metadata)
    dataset_dir = dataset_dir_for_manifest(manifest, biotope_root).resolve()
    mapping: dict[str, str] = {}
    for old, new in moves:
        present = old if old.exists() else new
        for distribution in metadata.get("distribution", []):
            url = distribution.get("contentUrl")
            if distribution.get("@type") != FILE_OBJECT_TYPE or not isinstance(url, str):
                continue
            if url == old.relative_to(biotope_root).as_posix():
                distribution["contentUrl"] = new.relative_to(biotope_root).as_posix()
            elif (dataset_dir / url).resolve() == old.resolve():
                distribution["contentUrl"] = Path(os.path.relpath(new, dataset_dir)).as_posix()
            else:
                continue
            mapping |= moved_ids(metadata, distribution["@id"], _within(old, dataset_dir), _within(new, dataset_dir))
            distribution.pop(MOVED_FROM, None)
            distribution["sha256"] = checksum or calculate_file_checksum(present)
            distribution["dateModified"] = datetime.now(timezone.utc).isoformat()
            distribution["contentSize"] = present.stat().st_size
    if not mapping:
        return None
    rename(metadata, mapping)
    own = [new for old, new in moves if manifest == manifest_for(old, biotope_root)]
    found = annotation.located(manifest)
    text = annotation.renamed(found, renamer(mapping)) if found is not None else None
    after = annotation.current(metadata, annotation.parsed(found, text) if found and text else annotation.read(found))
    schemas, revised = planned_ids(biotope_root / "graph/sources", manifest, before, after, mapping)
    target = manifest_for(own[0], biotope_root) if own else manifest
    moved = annotation.annotation_path(own[0]) if own and found is not None else found
    return _Plan(manifest, target, description_text(after), moved, text, schemas, revised)


def _apply(source: Path, destination: Path, plans: list[_Plan], biotope_root: Path, console: Console) -> None:
    sources = biotope_root / "graph/sources"
    kept = [
        *(path for plan in plans for path in (plan.manifest, plan.target, plan.annotation) if path is not None),
        *(path for plan in plans for path in package_files(sources, plan.manifest)),
        *(annotation.annotation_path(path) for path in (source, destination) if not source.is_dir()),
    ]
    saved = {path: path.read_bytes() if path.is_file() else None for path in kept}
    try:
        shutil.move(str(source), str(destination))
    except OSError as exc:
        console.print(f"[bold red]❌ Failed to move: {exc}[/]")
        raise click.Abort from exc
    written: list[Path] = []
    try:
        if destination.is_file():
            _move_annotation(source, destination, biotope_root)
        for plan in plans:
            if plan.annotation is not None and plan.annotation_text is not None:
                write_text_atomic(plan.annotation, plan.annotation_text)
                written.append(plan.annotation)
            write_text_atomic(plan.manifest, plan.text)
            written += [plan.target, *write_ids(plan.manifest, plan.schemas, plan.revised)]
            if plan.target != plan.manifest:
                plan.target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    _move_manifest(biotope_root, plan.manifest, plan.target)
                except OSError as exc:
                    raise OSError(f"Failed to move metadata file {plan.manifest}: {exc}") from exc
    except Exception as exc:
        for path, data in saved.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                (write_module if path.suffix == ".py" else write_text_atomic)(path, data.decode("utf-8"))
        shutil.move(str(destination), str(source))
        console.print(f"[bold red]❌ {exc}; nothing was moved.[/]")
        raise click.Abort from exc
    warn_ignored(biotope_root, [path for path in written if path.exists()])


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

    owners = {manifest for path in tracked_files for manifest in _find_metadata_files_for_file(path, biotope_root)}
    if all(_encloses(dataset_dir_for_manifest(manifest, biotope_root), source) for manifest in owners):
        destination.parent.mkdir(parents=True, exist_ok=True)
        moves = [(path, destination / path.relative_to(source)) for path in tracked_files]
        plans = _planned(sorted(owners), moves, biotope_root)
        _apply(source, destination, plans, biotope_root, console)
        console.print(
            Panel(
                f"[bold green]✅ Moved directory:[/] {source}\n"
                f"[bold green]To:[/] {destination}\n"
                f"[bold blue]📝 Updated {len(plans)} metadata file(s) in place[/]",
                title="Directory Move Complete",
            )
        )
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
            for manifest in destination_metadata_dir.rglob("*.jsonld") if not rollback_needed else ():
                old_manifest = source_metadata_dir / manifest.relative_to(destination_metadata_dir)
                warn_ignored(biotope_root, follow_manifest(biotope_root / "graph/sources", old_manifest, manifest))

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
                        new_metadata_path = manifest_for(new_file_path, biotope_root)

                        # Move the metadata file to mirror the new data file structure
                        if new_metadata_path != metadata_file:
                            new_metadata_path.parent.mkdir(parents=True, exist_ok=True)
                            try:
                                _move_manifest(biotope_root, metadata_file, new_metadata_path)
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

    warn_ignored(biotope_root, [path for path in updated_files if path.exists()])

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


def _encloses(dataset_dir: Path, directory: Path) -> bool:
    return directory.is_relative_to(dataset_dir) and directory != dataset_dir


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
            _move_manifest(biotope_root, old, new)
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

    warn_ignored(biotope_root, rewritten)
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

    write_description(manifest_path, metadata)


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


def _update_metadata_file_path(
    metadata_file: Path,
    old_path: str,
    new_path: str,
    new_checksum: str,
    biotope_root: Path,
) -> bool:
    """Update file path in a metadata file."""
    try:
        plan = _plan(metadata_file, [(biotope_root / old_path, biotope_root / new_path)], biotope_root, new_checksum)
    except (json.JSONDecodeError, IOError, OSError, ValueError):
        return False
    if plan is None:
        return False
    if plan.annotation is not None and plan.annotation_text is not None:
        write_text_atomic(plan.annotation, plan.annotation_text)
    write_text_atomic(metadata_file, plan.text)
    warn_ignored(biotope_root, [metadata_file, *write_ids(metadata_file, plan.schemas, plan.revised)])
    return True


def _move_manifest(biotope_root: Path, old: Path, new: Path) -> None:
    shutil.move(str(old), str(new))
    warn_ignored(biotope_root, follow_manifest(biotope_root / "graph/sources", old, new))


def _within(path: Path, dataset_dir: Path) -> str:
    return (path.relative_to(dataset_dir) if path.is_relative_to(dataset_dir) else Path(path.name)).as_posix()
