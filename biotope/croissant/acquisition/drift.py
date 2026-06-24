"""Detect when on-disk data has changed since a Croissant manifest was baked.

Editing files under ``datasets_location`` after ``biotope add`` baked the
Croissant JSON-LD (e.g. adding a column to a CSV) leaves the manifest's field
list stale: a mapping can't see the new column until the directory is
re-baked. There's no per-file checksum recorded for FileSet-described data
(a FileSet covers a glob, not one file), so this uses mtime as a cheap,
file-content-agnostic proxy: any data file newer than the manifest itself is
a drift candidate.
"""

from __future__ import annotations

from pathlib import Path

from biotope.metadata import SCAFFOLD_FILENAME


def detect_manifest_drift(croissant_path: str | Path, datasets_location: str | Path) -> list[Path]:
    """Return data files modified more recently than the Croissant manifest.

    An empty list means no drift detected (or the manifest/location doesn't
    exist — callers should treat that as "nothing to warn about", not an
    error). Best-effort and coarse-grained: it does not parse which files
    belong to which record set, just whether *anything* under
    ``datasets_location`` moved after the manifest was last written.

    ``SCAFFOLD_FILENAME`` (``.biotope.yaml``) is excluded: ``biotope add``
    writes it into the same directory right after baking the manifest, so it
    is always newer by construction and would otherwise register as drift on
    every single ``add``, regardless of whether the data actually changed.
    """
    croissant_path = Path(croissant_path)
    datasets_location = Path(datasets_location)
    if not croissant_path.is_file() or not datasets_location.is_dir():
        return []

    manifest_mtime = croissant_path.stat().st_mtime
    drifted: list[Path] = []
    for candidate in datasets_location.rglob("*"):
        if not candidate.is_file() or candidate.name == SCAFFOLD_FILENAME:
            continue
        if candidate.stat().st_mtime > manifest_mtime:
            drifted.append(candidate)
    return drifted
