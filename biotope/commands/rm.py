"""``biotope rm`` — remove a tracked dataset or a single file from a manifest.

Two modes that mirror how ``biotope add`` introduces things:

* **Whole-dataset:** ``biotope rm data/raw/kidney_pdf`` — delete the data
  directory and its manifest at ``.biotope/datasets/data/raw/kidney_pdf.jsonld``.
* **Single file in a multi-file manifest:** ``biotope rm data/raw/things/foo.csv``
  — drop the matching ``cr:FileObject`` from the manifest covering the file's
  dataset directory, and delete the file on disk.

By default the data is deleted alongside the manifest entry (matches ``git
rm``). Pass ``--keep-data`` to untrack only and leave the files on disk.

FileSet-covered files are refused for now: removing one without rewriting the
FileSet's ``includes``/``excludes`` would leave the manifest claiming a glob
that no longer matches reality. Either delete the whole dataset, or hand-edit
the manifest.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm

from biotope.commands.add import _resolve_dataset_ref
from biotope.metadata import (
    FILE_OBJECT_TYPE,
    dataset_dir_for_manifest,
    file_coverage_in_manifest,
    find_owning_manifest,
)
from biotope.utils import find_biotope_root, stage_git_changes


console = Console()


@click.command()
@click.argument("target", type=click.Path(path_type=Path))
@click.option(
    "--keep-data",
    is_flag=True,
    help="Drop from tracking but leave the data on disk (cf. `git rm --cached`).",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Skip the confirmation prompt.",
)
def rm(target: Path, keep_data: bool, force: bool) -> None:
    """Remove a dataset or a file from biotope tracking.

    Symmetric with `biotope add`: a directory argument removes the whole
    dataset (data + manifest); a file argument drops just that file's
    `cr:FileObject` from its owning manifest. If the manifest then has no
    distribution entries left, it's deleted too.
    """
    biotope_root = find_biotope_root()
    if biotope_root is None:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort

    if not target.is_absolute():
        target = (Path.cwd() / target).resolve()

    if target.is_dir():
        _remove_whole_dataset(target, biotope_root, keep_data=keep_data, force=force)
        return
    if target.is_file():
        _remove_single_file(target, biotope_root, keep_data=keep_data, force=force)
        return

    # Path doesn't exist on disk — accept canonical dataset id (`biotope rm
    # data/raw/kidney_pdf` after the dir is already gone, for example).
    try:
        rel_id = _resolve_dataset_ref(str(target), biotope_root)
    except ValueError as exc:
        click.echo(f"❌ {target}: {exc}")
        raise click.Abort from exc

    manifest = biotope_root / ".biotope" / "datasets" / f"{rel_id}.jsonld"
    data_dir = biotope_root / rel_id
    _remove_whole_dataset(data_dir, biotope_root, keep_data=keep_data, force=force, manifest_override=manifest)


def _remove_whole_dataset(
    data_dir: Path,
    biotope_root: Path,
    *,
    keep_data: bool,
    force: bool,
    manifest_override: Path | None = None,
) -> None:
    """Delete the data directory (unless --keep-data) and the manifest."""
    if manifest_override is not None:
        manifest = manifest_override
    else:
        rel = data_dir.relative_to(biotope_root)
        manifest = biotope_root / ".biotope" / "datasets" / f"{rel}.jsonld"

    if not manifest.is_file():
        click.echo(
            f"❌ {data_dir.relative_to(biotope_root) if data_dir.is_relative_to(biotope_root) else data_dir} "
            "is not a tracked dataset (no manifest under .biotope/datasets/)."
        )
        click.echo("   If you wanted to remove a single tracked file, pass the file path instead.")
        raise click.Abort

    if not force:
        what = "manifest" if keep_data else "data directory and manifest"
        if not Confirm.ask(
            f"Remove {what} for [cyan]{manifest.relative_to(biotope_root)}[/cyan]?",
            default=False,
        ):
            click.echo("Aborted.")
            return

    manifest.unlink()
    _prune_empty_manifest_parents(manifest, biotope_root)

    if not keep_data and data_dir.is_dir():
        shutil.rmtree(data_dir)

    stage_git_changes(biotope_root)
    console.print(
        f"[green]✓[/green] Removed dataset [cyan]{manifest.stem}[/cyan]" + ("" if keep_data else " (data deleted)")
    )


def _remove_single_file(
    file_path: Path,
    biotope_root: Path,
    *,
    keep_data: bool,
    force: bool,
) -> None:
    """Drop a single `cr:FileObject` from its owning manifest.

    The file's owning manifest is the one whose dataset_dir is the file's
    closest ancestor. If the file is only covered by a `cr:FileSet` glob,
    refuse — that requires rewriting the manifest's includes/excludes which
    is out of scope here.
    """
    manifest_path = find_owning_manifest(file_path, biotope_root)
    if manifest_path is None:
        click.echo(f"❌ {file_path}: no manifest tracks this file.")
        raise click.Abort

    with open(manifest_path) as handle:
        metadata = json.load(handle)
    dataset_dir = dataset_dir_for_manifest(manifest_path, biotope_root)
    coverage = file_coverage_in_manifest(metadata, dataset_dir, file_path, biotope_root)

    if coverage == "fileset":
        click.echo(
            f"❌ {file_path.relative_to(biotope_root)} is covered by a FileSet glob in "
            f"{manifest_path.relative_to(biotope_root)}.\n"
            "   Removing one FileSet-covered file would leave the manifest's `includes` "
            "pattern stale.\n   Either remove the whole dataset, or hand-edit the manifest."
        )
        raise click.Abort

    file_rel = str(file_path.relative_to(biotope_root))
    distribution = metadata.get("distribution", []) or []
    before = len(distribution)
    metadata["distribution"] = [
        d for d in distribution if not (d.get("@type") == FILE_OBJECT_TYPE and d.get("contentUrl") == file_rel)
    ]
    if len(metadata["distribution"]) == before:
        click.echo(f"❌ {file_rel}: no matching FileObject in {manifest_path}.")
        raise click.Abort

    if not force:
        what = "file" if keep_data else "tracking entry and the file on disk"
        if not Confirm.ask(
            f"Remove {what} for [cyan]{file_rel}[/cyan]?",
            default=False,
        ):
            click.echo("Aborted.")
            return

    # If the manifest has no distribution entries left, treat the file as a
    # single-file dataset and remove the manifest entirely.
    manifest_gone = False
    if not metadata["distribution"]:
        manifest_path.unlink()
        _prune_empty_manifest_parents(manifest_path, biotope_root)
        manifest_gone = True
    else:
        with open(manifest_path, "w") as handle:
            json.dump(metadata, handle, indent=2)

    if not keep_data and file_path.is_file():
        file_path.unlink()

    stage_git_changes(biotope_root)
    msg = f"[green]✓[/green] Untracked [cyan]{file_rel}[/cyan]"
    if not keep_data:
        msg += " (file deleted)"
    if manifest_gone:
        msg += f" — manifest {manifest_path.relative_to(biotope_root)} was empty and removed"
    console.print(msg)


def _prune_empty_manifest_parents(manifest_path: Path, biotope_root: Path) -> None:
    """Walk up under `.biotope/datasets/`, removing empty directories."""
    datasets_root = biotope_root / ".biotope" / "datasets"
    current = manifest_path.parent
    while current != datasets_root and current.is_dir():
        try:
            if any(current.iterdir()):
                return
            current.rmdir()
        except OSError:
            return
        current = current.parent
