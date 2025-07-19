"""Move command implementation for tracking data files and updating metadata."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import click
from rich.console import Console
from rich.panel import Panel

from biotope.commands.add import (
    calculate_file_checksum,
    is_file_tracked,
    _stage_git_changes,
)
from biotope.utils import find_biotope_root, is_git_repo


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
            click.echo(
                f"❌ '{source}' is a directory. Use --recursive (-r) to move directories."
            )
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
    actual_destination = _validate_move_operation(
        source, destination, biotope_root, force
    )

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
        click.echo(
            f"❌ Destination '{actual_destination}' exists. Use --force to overwrite."
        )
        raise click.Abort

    return actual_destination


def _execute_move(
    source: Path, destination: Path, biotope_root: Path, console: Console
) -> None:
    """Execute the actual move operation."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    metadata_files = _find_metadata_files_for_file(source, biotope_root)

    if not metadata_files:
        click.echo("⚠️  No metadata files found referencing this file")
        return

    # Move the actual data file
    shutil.move(str(source), str(destination))

    new_checksum = calculate_file_checksum(destination)

    # Calculate source and destination relative paths for metadata file naming
    source_rel = source.relative_to(biotope_root)
    destination_rel = destination.relative_to(biotope_root)

    updated_files = []
    moved_metadata_files = []

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
            new_metadata_path = (
                biotope_root
                / ".biotope"
                / "datasets"
                / destination_rel.with_suffix(".jsonld")
            )

            # Move the metadata file to mirror the new data file structure
            if new_metadata_path != metadata_file:
                new_metadata_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(metadata_file), str(new_metadata_path))
                moved_metadata_files.append((metadata_file, new_metadata_path))

    if updated_files or moved_metadata_files:
        _stage_git_changes(biotope_root)

    console.print(
        Panel(
            f"[bold green]✅ Moved:[/] {source}\n"
            f"[bold green]To:[/] {destination}\n"
            f"[bold blue]📝 Updated {len(updated_files)} metadata file(s)[/]"
            + (
                f"\n[bold blue]📁 Moved {len(moved_metadata_files)} metadata file(s)[/]"
                if moved_metadata_files
                else ""
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


def _execute_directory_move(
    source: Path, destination: Path, biotope_root: Path, console: Console
) -> None:
    """Execute move operation for a directory and all its tracked files."""
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
    is_simple_rename = (
        source.parent == destination.parent and source_metadata_dir.exists()
    )

    # Ensure destination directory exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Move the entire directory structure
    shutil.move(str(source), str(destination))

    updated_files = []
    total_files_moved = len(tracked_files)

    if is_simple_rename and source_metadata_dir.exists():
        # For simple renames, rename the entire metadata directory structure
        destination_metadata_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_metadata_dir), str(destination_metadata_dir))

        # Update all metadata files in the renamed directory
        for metadata_file in destination_metadata_dir.rglob("*.jsonld"):
            # Read the metadata to find what file it references
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)

                # Find file objects in the metadata
                for distribution in metadata.get("distribution", []):
                    if distribution.get("@type") == "sc:FileObject":
                        old_content_url = distribution.get("contentUrl")
                        if old_content_url and old_content_url.startswith(
                            str(source_rel)
                        ):
                            # Update the path from source to destination
                            new_content_url = old_content_url.replace(
                                str(source_rel), str(destination_rel), 1
                            )
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
            except (json.JSONDecodeError, IOError):
                continue
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
            new_checksum = calculate_file_checksum(new_file_path)

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
                    new_metadata_path = (
                        biotope_root
                        / ".biotope"
                        / "datasets"
                        / new_rel_path.with_suffix(".jsonld")
                    )

                    # Move the metadata file to mirror the new data file structure
                    if new_metadata_path != metadata_file:
                        new_metadata_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(metadata_file), str(new_metadata_path))
                        moved_metadata_files.append((metadata_file, new_metadata_path))

        # Clean up empty directories in the old metadata location
        _cleanup_empty_metadata_directories(source_metadata_dir, biotope_root)

    if updated_files:
        _stage_git_changes(biotope_root)

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
    """Find all metadata files that reference a given data file."""
    file_rel_path = str(file_path.relative_to(biotope_root))
    metadata_files = []

    datasets_dir = biotope_root / ".biotope" / "datasets"
    if not datasets_dir.exists():
        return metadata_files

    for metadata_file in datasets_dir.rglob("*.jsonld"):
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)
                for distribution in metadata.get("distribution", []):
                    if (
                        distribution.get("@type") == "sc:FileObject"
                        and distribution.get("contentUrl") == file_rel_path
                    ):
                        metadata_files.append(metadata_file)
                        break
        except (json.JSONDecodeError, IOError):
            continue

    return metadata_files


def _update_metadata_file_path(
    metadata_file: Path,
    old_path: str,
    new_path: str,
    new_checksum: str,
    biotope_root: Path,
) -> bool:
    """Update file path in a metadata file."""
    try:
        with open(metadata_file) as f:
            metadata = json.load(f)

        updated = False
        for distribution in metadata.get("distribution", []):
            if (
                distribution.get("@type") == "sc:FileObject"
                and distribution.get("contentUrl") == old_path
            ):
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

    except (json.JSONDecodeError, IOError):
        return False
