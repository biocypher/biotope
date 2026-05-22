"""Shared Croissant metadata helpers for biotope commands."""

from __future__ import annotations

import copy
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from biotope.utils import calculate_file_checksum


FILE_OBJECT_TYPE = "cr:FileObject"
LEGACY_FILE_OBJECT_TYPE = "sc:FileObject"


SCAFFOLD_FILENAME = ".biotope.yaml"


@dataclass(frozen=True)
class DatasetTarget:
    """Resolved dataset metadata target inside a biotope project."""

    input_path: Path
    metadata_path: Path
    dataset_dir: Path
    scaffold_path: Path


def get_standard_context() -> dict[str, str]:
    """Get the standard Croissant context."""
    return {
        "@vocab": "https://schema.org/",
        "cr": "https://mlcommons.org/croissant/",
        "ml": "http://ml-schema.org/",
        "sc": "https://schema.org/",
        "dct": "http://purl.org/dc/terms/",
        "data": "https://mlcommons.org/croissant/data/",
        "rai": "https://mlcommons.org/croissant/rai/",
        "format": "https://mlcommons.org/croissant/format/",
        "citeAs": "https://mlcommons.org/croissant/citeAs/",
        "conformsTo": "https://mlcommons.org/croissant/conformsTo/",
        "@language": "en",
        "repeated": "https://mlcommons.org/croissant/repeated/",
        "field": "https://mlcommons.org/croissant/field/",
        "examples": "https://mlcommons.org/croissant/examples/",
        "recordSet": "https://mlcommons.org/croissant/recordSet/",
        "fileObject": "https://mlcommons.org/croissant/fileObject/",
        "fileSet": "https://mlcommons.org/croissant/fileSet/",
        "source": "https://mlcommons.org/croissant/source/",
        "references": "https://mlcommons.org/croissant/references/",
        "key": "https://mlcommons.org/croissant/key/",
        "parentField": "https://mlcommons.org/croissant/parentField/",
        "isLiveDataset": "https://mlcommons.org/croissant/isLiveDataset/",
        "separator": "https://mlcommons.org/croissant/separator/",
        "extract": "https://mlcommons.org/croissant/extract/",
        "subField": "https://mlcommons.org/croissant/subField/",
        "regex": "https://mlcommons.org/croissant/regex/",
        "column": "https://mlcommons.org/croissant/column/",
        "path": "https://mlcommons.org/croissant/path/",
        "fileProperty": "https://mlcommons.org/croissant/fileProperty/",
        "md5": "https://mlcommons.org/croissant/md5/",
        "jsonPath": "https://mlcommons.org/croissant/jsonPath/",
        "transform": "https://mlcommons.org/croissant/transform/",
        "replace": "https://mlcommons.org/croissant/replace/",
        "dataType": "https://mlcommons.org/croissant/dataType/",
        "includes": "https://mlcommons.org/croissant/includes/",
        "excludes": "https://mlcommons.org/croissant/excludes/",
    }


def merge_metadata(dynamic_metadata: dict[str, Any]) -> dict[str, Any]:
    """Merge dynamic metadata with the standard Croissant skeleton."""
    metadata = {
        "@context": get_standard_context(),
        "@type": "sc:Dataset",
    }
    metadata.update(dynamic_metadata)
    return metadata


def normalize_metadata_shape(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with uniform Croissant keys; reject legacy sc:FileObject."""
    normalized = copy.deepcopy(metadata)

    if "cr:recordSet" in normalized:
        record_sets = normalized.pop("cr:recordSet") or []
        normalized.setdefault("recordSet", [])
        normalized["recordSet"].extend(record_sets)

    for record_set in normalized.get("recordSet", []) or []:
        if "cr:field" in record_set:
            fields = record_set.pop("cr:field") or []
            record_set.setdefault("field", [])
            record_set["field"].extend(fields)

    ensure_no_legacy_file_objects(normalized)
    return normalized


def ensure_no_legacy_file_objects(metadata: dict[str, Any]) -> None:
    """Raise when legacy file object types are present."""
    for distribution in metadata.get("distribution", []) or []:
        if distribution.get("@type") == LEGACY_FILE_OBJECT_TYPE:
            raise ValueError(
                "Legacy sc:FileObject is no longer supported. "
                "Please regenerate the metadata with `biotope add`."
            )


def dataset_dir_for_manifest(manifest_path: Path, biotope_root: Path) -> Path:
    """The data directory mirrored by a manifest under the project root.

    Manifests live at ``.biotope/datasets/<rel>.jsonld``; the data they cover
    lives at ``<biotope_root>/<rel>/``.
    """
    datasets_dir = biotope_root / ".biotope" / "datasets"
    rel = manifest_path.relative_to(datasets_dir).with_suffix("")
    return biotope_root / rel


def file_coverage_in_manifest(
    metadata: dict[str, Any],
    manifest_dataset_dir: Path,
    file_path: Path,
    biotope_root: Path,
) -> str | None:
    """Return how ``file_path`` is covered by ``metadata``, or ``None``.

    Result is one of:

    * ``"file_object"`` — an explicit ``cr:FileObject`` with matching
      ``contentUrl``.
    * ``"fileset"`` — covered only by a ``cr:FileSet`` ``includes`` glob.
    * ``None`` — not covered at all.

    FileSet patterns are matched with ``Path.glob`` against the manifest's
    dataset directory, mirroring how ``biotope add`` resolves them at bake
    time.
    """
    try:
        file_rel = str(file_path.relative_to(biotope_root))
    except ValueError:
        return None

    fileset_hit = False
    for distribution in metadata.get("distribution", []) or []:
        entry_type = distribution.get("@type")
        if entry_type == FILE_OBJECT_TYPE:
            if distribution.get("contentUrl") == file_rel:
                return "file_object"
            continue
        if entry_type == "cr:FileSet" and not fileset_hit:
            if _fileset_covers(distribution, manifest_dataset_dir, file_path):
                fileset_hit = True

    return "fileset" if fileset_hit else None


def _fileset_covers(
    fileset: dict[str, Any], dataset_dir: Path, file_path: Path
) -> bool:
    if not dataset_dir.is_dir():
        return False
    includes = fileset.get("includes")
    patterns = [includes] if isinstance(includes, str) else list(includes or [])
    file_resolved = file_path.resolve()
    for pattern in patterns:
        for candidate in dataset_dir.glob(pattern):
            if candidate.is_file() and candidate.resolve() == file_resolved:
                return True
    return False


def find_owning_manifest(file_path: Path, biotope_root: Path) -> Path | None:
    """Return the manifest that covers ``file_path``, preferring the deepest.

    "Deepest" means the manifest whose dataset directory is the longest
    ancestor of ``file_path``. When multiple manifests legitimately cover a
    file (e.g. nested `biotope add` calls), the innermost one wins.
    Returns ``None`` when no manifest covers the file.
    """
    datasets_dir = biotope_root / ".biotope" / "datasets"
    if not datasets_dir.is_dir():
        return None

    import json

    best: tuple[int, Path] | None = None
    for manifest_path in datasets_dir.rglob("*.jsonld"):
        try:
            with open(manifest_path) as handle:
                metadata = json.load(handle)
        except (OSError, ValueError):
            continue
        dataset_dir = dataset_dir_for_manifest(manifest_path, biotope_root)
        if file_coverage_in_manifest(metadata, dataset_dir, file_path, biotope_root) is None:
            continue
        depth = len(dataset_dir.parts)
        if best is None or depth > best[0]:
            best = (depth, manifest_path)
    return best[1] if best else None


def resolve_target(path: Path, biotope_root: Path) -> DatasetTarget:
    """Resolve a file, dir, csv, or jsonld path to one dataset metadata target."""
    resolved = path.resolve()
    datasets_dir = biotope_root / ".biotope" / "datasets"

    if resolved.suffix == ".jsonld":
        metadata_path = resolved
        try:
            rel_metadata = metadata_path.relative_to(datasets_dir)
        except ValueError as exc:
            raise ValueError(f"JSON-LD target '{path}' is outside .biotope/datasets") from exc
        dataset_dir = biotope_root / rel_metadata.with_suffix("")
        return DatasetTarget(
            input_path=resolved,
            metadata_path=metadata_path,
            dataset_dir=dataset_dir,
            scaffold_path=dataset_dir / SCAFFOLD_FILENAME,
        )

    if resolved.is_dir():
        rel_dir = resolved.relative_to(biotope_root)
        metadata_path = (datasets_dir / rel_dir).with_suffix(".jsonld")
        return DatasetTarget(
            input_path=resolved,
            metadata_path=metadata_path,
            dataset_dir=resolved,
            scaffold_path=resolved / SCAFFOLD_FILENAME,
        )

    if resolved.name == SCAFFOLD_FILENAME:
        dataset_dir = resolved.parent
        rel_dir = dataset_dir.relative_to(biotope_root)
        metadata_path = (datasets_dir / rel_dir).with_suffix(".jsonld")
        return DatasetTarget(
            input_path=resolved,
            metadata_path=metadata_path,
            dataset_dir=dataset_dir,
            scaffold_path=resolved,
        )

    rel_file = resolved.relative_to(biotope_root)
    metadata_path = (datasets_dir / rel_file).with_suffix(".jsonld")
    return DatasetTarget(
        input_path=resolved,
        metadata_path=metadata_path,
        dataset_dir=resolved.parent,
        scaffold_path=resolved.parent / SCAFFOLD_FILENAME,
    )


def make_file_object(
    file_path: Path,
    biotope_root: Path,
    *,
    object_id: str | None = None,
) -> dict[str, Any]:
    """Build a normalized Croissant FileObject for one physical file."""
    relative_path = file_path.relative_to(biotope_root)
    sha256_hash = calculate_file_checksum(file_path)
    encoding_format = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"

    return {
        "@type": FILE_OBJECT_TYPE,
        "@id": object_id or f"file_{sha256_hash[:8]}",
        "name": file_path.name,
        "contentUrl": str(relative_path),
        "encodingFormat": encoding_format,
        "sha256": sha256_hash,
        "contentSize": str(file_path.stat().st_size),
    }


@dataclass(frozen=True)
class DatasetStats:
    """Structural counts derived from one Croissant Dataset JSON-LD."""

    record_sets: int
    file_sets: int
    file_objects: int
    record_set_details: tuple[tuple[str, int], ...]  # (name, field_count) per RecordSet


def summarize_metadata(metadata: dict[str, Any]) -> DatasetStats:
    """Count RecordSets, FileSets, FileObjects, and per-RecordSet field counts."""
    record_sets = metadata.get("recordSet", []) or []
    distributions = metadata.get("distribution", []) or []

    file_set_count = sum(1 for d in distributions if d.get("@type") == "cr:FileSet")
    file_object_count = sum(1 for d in distributions if d.get("@type") == FILE_OBJECT_TYPE)

    details: list[tuple[str, int]] = []
    for record_set in record_sets:
        name = record_set.get("name") or record_set.get("@id") or "?"
        fields = record_set.get("field", []) or []
        details.append((str(name), len(fields)))

    return DatasetStats(
        record_sets=len(record_sets),
        file_sets=file_set_count,
        file_objects=file_object_count,
        record_set_details=tuple(details),
    )


def parse_key_value_pairs(pairs: tuple[str, ...], option_name: str) -> dict[str, str]:
    """Parse repeated KEY=VALUE CLI options into a dict."""
    parsed: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid {option_name} value '{pair}'. Expected KEY=VALUE.")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid {option_name} value '{pair}'. Key cannot be empty.")
        parsed[key] = value
    return parsed

