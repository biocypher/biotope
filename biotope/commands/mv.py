import copy
import fnmatch
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

import click
from rich.console import Console
from rich.panel import Panel

from biotope.croissant import annotation
from biotope.croissant.ids import MOVED_FROM, moved_ids, rename, renamer
from biotope.extraction.run import STATES, state_path
from biotope.graph.moves import carry_description, package_files, planned_ids, prune, write_ids
from biotope.graph.sources import description_text, write_module, write_text_atomic
from biotope.graph.targets import Target
from biotope.metadata import FILE_OBJECT_TYPE, dataset_id, ensure_no_legacy_file_objects, manifest_for
from biotope.utils import calculate_file_checksum, find_biotope_root, is_file_tracked, warn_ignored


@click.command()
@click.argument("source", type=click.Path(exists=True, path_type=Path))
@click.argument("destination", type=click.Path(path_type=Path))
@click.option("--force", "-f", is_flag=True, help="Overwrite destination if it exists")
@click.option("--recursive", "-r", is_flag=True, help="Move directories recursively")
def mv(source: Path, destination: Path, force: bool, recursive: bool) -> None:
    """Move a tracked file or directory and update every description, source package and state that names it."""
    console = Console()
    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort
    source, destination = Path(os.path.abspath(source)), Path(os.path.abspath(destination))
    if source.is_dir() and not recursive:
        click.echo(f"❌ '{source}' is a directory. Use --recursive (-r) to move directories.")
        raise click.Abort
    files = sorted(path for path in source.rglob("*") if path.is_file()) if source.is_dir() else [source]
    if not any(is_file_tracked(path, biotope_root) for path in files):
        click.echo(
            f"❌ Directory '{source}' contains no tracked files."
            if source.is_dir()
            else f"❌ File '{source}' is not tracked. Use 'biotope add' first."
        )
        raise click.Abort
    destination = _validate_move_operation(source, destination, biotope_root, force)
    moves = {path: _follows(path, source, destination) for path in files}
    plans = _planned(source, destination, moves, biotope_root)
    _apply(source, destination, moves, plans, biotope_root, console)
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


def _resolve_destination_path(source: Path, destination: Path) -> Path:
    return destination / source.name if destination.is_dir() else destination


def _validate_move_operation(source: Path, destination: Path, biotope_root: Path, force: bool) -> Path:
    actual_destination = _resolve_destination_path(source, destination)
    if not actual_destination.is_relative_to(biotope_root):
        click.echo("❌ Cannot move file outside biotope project")
        raise click.Abort
    if source.resolve() == actual_destination.resolve():
        click.echo("❌ Source and destination are the same")
        raise click.Abort
    if source.is_relative_to(biotope_root / ".biotope"):
        click.echo("❌ Cannot move biotope internal files")
        raise click.Abort
    if actual_destination.exists() and not force:
        click.echo(f"❌ Destination '{actual_destination}' exists. Use --force to overwrite.")
        raise click.Abort
    return actual_destination


def _follows(path: Path, source: Path, destination: Path) -> Path:
    if source.is_file() and path == annotation.annotation_path(source):
        return annotation.annotation_path(destination)
    return destination / path.relative_to(source) if path.is_relative_to(source) else path


class _Refused(Exception):
    pass


@dataclass
class _Plan:
    manifest: Path
    target: Path
    text: str
    annotation: Path | None
    annotation_target: Path | None
    annotation_text: str | None
    schemas: dict[Path, str]
    revised: list[Target]


def _planned(source: Path, destination: Path, moves: dict[Path, Path], biotope_root: Path) -> list[_Plan]:
    datasets = biotope_root / ".biotope" / "datasets"
    plans: list[_Plan] = []
    for manifest in sorted(datasets.rglob("*.jsonld")):
        data = biotope_root / dataset_id(manifest, biotope_root)
        carried = _follows(data, source, destination)
        try:
            metadata = _load_metadata_file(manifest)
        except (OSError, ValueError) as exc:
            if carried == data:
                continue
            _refuse(f"Cannot update {manifest.relative_to(biotope_root)}: {exc}")
        try:
            plan = _plan(manifest, metadata, data, carried, source, destination, moves, biotope_root)
        except _Refused as refusal:
            _refuse(str(refusal))
        except (OSError, ValueError) as exc:
            _refuse(f"Cannot update {manifest.relative_to(biotope_root)}: {exc}")
        if plan is not None:
            plans.append(plan)
    moving = {plan.manifest for plan in plans}
    for plan in plans:
        if plan.target != plan.manifest and plan.target.exists() and plan.target not in moving:
            _refuse(f"Destination manifest already exists: {plan.target.relative_to(biotope_root)}")
    return plans


def _refuse(message: str) -> NoReturn:
    click.echo(f"❌ {message}")
    raise click.Abort


def _load_metadata_file(metadata_file: Path) -> dict[str, Any]:
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    ensure_no_legacy_file_objects(metadata)
    return metadata


def _plan(
    manifest: Path,
    metadata: dict[str, Any],
    data: Path,
    carried: Path,
    source: Path,
    destination: Path,
    moves: dict[Path, Path],
    biotope_root: Path,
) -> _Plan | None:
    folder = not data.is_file()
    base, new_base = (data, carried) if folder else (data.parent, carried.parent)
    staying = carried == data
    if staying and not source.is_relative_to(base):
        return None
    before = copy.deepcopy(metadata)
    mapping: dict[str, str] = {}
    now = datetime.now(timezone.utc).isoformat()
    for distribution in metadata.get("distribution") or []:
        url = distribution.get("contentUrl")
        if distribution.get("@type") != FILE_OBJECT_TYPE or not isinstance(url, str):
            continue
        old = _normal((base if folder else biotope_root) / url)
        new = moves.get(old)
        if new is None:
            continue
        if staying and not new.is_relative_to(base):
            raise _Refused(_cross_dataset(old, new, manifest, base, biotope_root))
        moved_url = new.relative_to(new_base if folder else biotope_root).as_posix()
        ids = moved_ids(
            metadata, distribution["@id"], old.relative_to(base).as_posix(), new.relative_to(new_base).as_posix()
        )
        if moved_url == url and all(old_id == new_id for old_id, new_id in ids.items()):
            continue
        mapping |= ids
        distribution["contentUrl"] = moved_url
        distribution.pop(MOVED_FROM, None)
        distribution["sha256"] = calculate_file_checksum(old)
        distribution["dateModified"] = now
        distribution["contentSize"] = old.stat().st_size
    if staying:
        _check_file_sets(manifest, metadata, base, moves, biotope_root)
        if not mapping:
            return None
    rename(metadata, mapping)
    old_name, new_name = (path.relative_to(biotope_root).as_posix() for path in (data, carried))
    for item in (metadata, metadata.get(annotation.FROM_DATA) or {}):
        if item.get("name") == old_name:
            item["name"] = new_name
    found = annotation.located(manifest)
    text = annotation.renamed(found, renamer(mapping)) if found is not None else None
    after = annotation.current(metadata, annotation.parsed(found, text) if found and text else annotation.read(found))
    schemas, revised = planned_ids(biotope_root / "graph/sources", manifest, before, after, mapping)
    moved_annotation = _follows(found, source, destination) if found is not None else None
    target = manifest if staying else manifest_for(carried, biotope_root)
    return _Plan(manifest, target, description_text(after), found, moved_annotation, text, schemas, revised)


def _normal(path: Path) -> Path:
    return Path(os.path.normpath(path))


def _cross_dataset(old: Path, new: Path, manifest: Path, base: Path, biotope_root: Path) -> str:
    return (
        f"Cross-dataset move refused. {old.relative_to(biotope_root)} is owned by "
        f"{manifest.relative_to(biotope_root)}, whose data lives under {base.relative_to(biotope_root)}/; "
        f"{new.relative_to(biotope_root)} is outside it. Use biotope add at the new location and biotope rm at the old."
    )


def _check_file_sets(
    manifest: Path, metadata: dict[str, Any], base: Path, moves: dict[Path, Path], biotope_root: Path
) -> None:
    patterns = _fileset_patterns(metadata)
    members = {_normal(path) for pattern in patterns for path in base.glob(pattern) if path.is_file()}
    for old in sorted(members & moves.keys()):
        new = moves[old]
        if not new.is_relative_to(base):
            raise _Refused(_cross_dataset(old, new, manifest, base, biotope_root))
        if not any(fnmatch.fnmatch(new.relative_to(base).as_posix(), pattern) for pattern in patterns):
            raise _Refused(
                f"FileSet pattern would no longer cover the file after rename. {old.relative_to(biotope_root)} is "
                f"covered by a FileSet glob ({', '.join(patterns)}) in {manifest.relative_to(biotope_root)}; "
                f"{new.relative_to(base).as_posix()} does not match it. Pick a name that does, or use rm and add."
            )


def _fileset_patterns(metadata: dict[str, Any]) -> list[str]:
    patterns: list[str] = []
    for distribution in metadata.get("distribution") or []:
        if distribution.get("@type") != "cr:FileSet":
            continue
        includes = distribution.get("includes")
        patterns += [includes] if isinstance(includes, str) else [p for p in includes or [] if isinstance(p, str)]
    return patterns


def _apply(
    source: Path, destination: Path, moves: dict[Path, Path], plans: list[_Plan], biotope_root: Path, console: Console
) -> None:
    states = {
        state_path(biotope_root, old): state_path(biotope_root, new)
        for old, new in moves.items()
        if state_path(biotope_root, old).is_file()
    }
    annotations = (
        {annotation.annotation_path(source): annotation.annotation_path(destination)} if source.is_file() else {}
    )
    kept = {
        *(path for plan in plans for path in (plan.manifest, plan.target, plan.annotation) if path is not None),
        *(path for plan in plans for path in package_files(biotope_root / "graph/sources", plan.manifest)),
        *(path for pair in [*states.items(), *annotations.items()] for path in pair),
    }
    saved = {path: path.read_bytes() if path.is_file() else None for path in kept}
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(source), str(destination))
    except OSError as exc:
        console.print(f"[bold red]❌ Failed to move: {exc}[/]")
        raise click.Abort from exc
    written: list[Path] = []
    try:
        for old, new in [*annotations.items(), *states.items()]:
            if old.is_file():
                new.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old), str(new))
                written.append(new)
        for plan in plans:
            if plan.annotation_target is not None and plan.annotation_text is not None:
                write_text_atomic(plan.annotation_target, plan.annotation_text)
                written.append(plan.annotation_target)
            write_text_atomic(plan.manifest, plan.text)
            written += [plan.target, *write_ids(plan.manifest, plan.schemas, plan.revised)]
            if plan.target != plan.manifest:
                written += carry_description(biotope_root, plan.manifest, plan.target)
    except Exception as exc:
        shutil.move(str(destination), str(source))
        for path, data in saved.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                (write_module if path.suffix == ".py" else write_text_atomic)(path, data.decode("utf-8"))
        console.print(f"[bold red]❌ {exc}; nothing was moved.[/]")
        raise click.Abort from exc
    for old in states:
        prune(old.parent, biotope_root / STATES)
    warn_ignored(biotope_root, [path for path in written if path.exists()])
