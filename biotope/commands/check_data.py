"""Check data integrity against recorded checksums."""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click
from rich.console import Console
from rich.table import Table

from biotope.utils import find_biotope_root


@click.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True, path_type=Path),
    help="Check specific file only",
)
@click.option(
    "--fix",
    is_flag=True,
    help="Attempt to fix corrupted files by re-downloading",
)
def check_data(file: Optional[Path], fix: bool) -> None:
    """
    Check data integrity against recorded checksums.
    
    Verifies that data files match their recorded SHA256 checksums.
    Reports any files that have been modified or corrupted.
    
    Args:
        file: Check specific file only
        fix: Attempt to fix corrupted files
    """
    console = Console()
    
    # Find biotope project root
    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    if file:
        # Check single file
        results = [_check_single_file(file, biotope_root)]
    else:
        # Check all tracked files
        results = check_all_files(biotope_root)

    # Display results
    _display_check_results(results, console, fix)


def _check_single_file(file_path: Path, biotope_root: Path) -> Dict:
    """Check integrity of a single file."""
    # Find the file's recorded checksum
    recorded_checksum = _get_recorded_checksum(file_path, biotope_root)
    
    if not recorded_checksum:
        return {
            "file_path": str(file_path),
            "status": "untracked",
            "message": "File not tracked in biotope"
        }
    
    # Calculate current checksum
    current_checksum = calculate_file_checksum(file_path)
    
    if current_checksum == recorded_checksum:
        return {
            "file_path": str(file_path),
            "status": "valid",
            "message": "Checksum matches"
        }
    else:
        return {
            "file_path": str(file_path),
            "status": "corrupted",
            "message": f"Checksum mismatch: expected {recorded_checksum[:8]}..., got {current_checksum[:8]}..."
        }


def check_all_files(biotope_root: Path) -> List[Dict]:
    """Check integrity of all tracked files."""
    results = []
    
    # Check files in datasets
    datasets_dir = biotope_root / ".biotope" / "datasets"
    if datasets_dir.exists():
        for dataset_file in datasets_dir.rglob("*.jsonld"):
            try:
                with open(dataset_file) as f:
                    metadata = json.load(f)
                    for distribution in metadata.get("distribution", []):
                        if distribution.get("@type") == "sc:FileObject":
                            content_url = distribution.get("contentUrl")
                            if content_url:
                                file_path = biotope_root / content_url
                                if file_path.exists():
                                    results.append(_check_single_file(file_path, biotope_root))
                                else:
                                    results.append({
                                        "file_path": str(file_path),
                                        "status": "missing",
                                        "message": "File not found"
                                    })
            except (json.JSONDecodeError, KeyError):
                continue
    
    return results


def _get_recorded_checksum(file_path: Path, biotope_root: Path) -> Optional[str]:
    """Get the recorded checksum for a file."""
    # Check datasets directory
    datasets_dir = biotope_root / ".biotope" / "datasets"
    if datasets_dir.exists():
        for dataset_file in datasets_dir.rglob("*.jsonld"):
            try:
                with open(dataset_file) as f:
                    metadata = json.load(f)
                    for distribution in metadata.get("distribution", []):
                        if distribution.get("@type") == "sc:FileObject":
                            content_url = distribution.get("contentUrl")
                            if content_url and (biotope_root / content_url) == file_path:
                                return distribution.get("sha256")
            except (json.JSONDecodeError, KeyError):
                continue
    
    return None


def calculate_file_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def _display_check_results(results: List[Dict], console: Console, fix: bool) -> None:
    """Display check results in a table."""
    if not results:
        console.print("No files to check.")
        return

    # Count results by status
    status_counts = {}
    for result in results:
        status = result["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    # Create table
    table = Table(title="Data Integrity Check Results")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Message", style="green")

    for result in results:
        status_style = {
            "valid": "green",
            "corrupted": "red",
            "missing": "yellow",
            "untracked": "blue"
        }.get(result["status"], "white")
        
        table.add_row(
            result["file_path"],
            f"[{status_style}]{result['status'].upper()}[/{status_style}]",
            result["message"]
        )

    console.print(table)

    # Summary
    console.print(f"\n[bold]Summary:[/]")
    for status, count in status_counts.items():
        color = {
            "valid": "green",
            "corrupted": "red",
            "missing": "yellow",
            "untracked": "blue"
        }.get(status, "white")
        console.print(f"  {status.upper()}: [{color}]{count}[/{color}]")

    # Recommendations
    if status_counts.get("corrupted", 0) > 0:
        console.print(f"\n[bold red]⚠️  Corrupted files detected![/]")
        if fix:
            console.print("Attempting to fix corrupted files...")
            # TODO: Implement fix logic
        else:
            console.print("Use --fix to attempt automatic repair")

    if status_counts.get("missing", 0) > 0:
        console.print(f"\n[bold yellow]⚠️  Missing files detected![/]")
        console.print("Some files referenced in metadata are missing from disk")


 