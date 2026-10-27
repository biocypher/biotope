"""Shared Croissant metadata helpers for biotope commands."""

from __future__ import annotations

import copy
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from biotope.croissant.ids import file_id
from biotope.utils import calculate_file_checksum


FILE_OBJECT_TYPE = "cr:FileObject"
LEGACY_FILE_OBJECT_TYPE = "sc:FileObject"


# biotope:status values — see docs/agent flow.
STATUS_RAW = "raw"
STATUS_PROCESSED = "processed"
STATUS_MAPPED = "mapped"
STATUS_VALUES = (STATUS_RAW, STATUS_PROCESSED, STATUS_MAPPED)
STATUS = "biotope:status"
DERIVED_FROM = "prov:wasDerivedFrom"


@dataclass(frozen=True)
class DatasetTarget:
    """Resolved dataset metadata target inside a biotope project."""

    input_path: Path
    metadata_path: Path
    dataset_dir: Path


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
        # biotope pipeline state (raw / processed / mapped). Placeholder URL —
        # rename when biotope picks a canonical namespace.
        "biotope": "https://biotope.org/ns/",
        # PROV-O for derivation provenance (e.g. an agent-produced JSON that
        # was derived from a raw PDF).
        "prov": "http://www.w3.org/ns/prov#",
    }


def merge_metadata(dynamic_metadata: dict[str, Any]) -> dict[str, Any]:
    """Merge dynamic metadata with the standard Croissant skeleton."""
    metadata = {
        "@context": get_standard_context(),
        "@type": "sc:Dataset",
    }
    metadata.update(dynamic_metadata)
    return metadata


def _coerce_list_fields(obj: Any, keys: tuple[str, ...] = ("field", "subField")) -> None:
    """Wrap lone dicts in lists for Croissant list-shaped keys (in-place)."""
    if isinstance(obj, dict):
        for key in keys:
            value = obj.get(key)
            if isinstance(value, dict):
                obj[key] = [value]
        for value in obj.values():
            if isinstance(value, list):
                for item in value:
                    _coerce_list_fields(item, keys)
            elif isinstance(value, dict):
                _coerce_list_fields(value, keys)
    elif isinstance(obj, list):
        for item in obj:
            _coerce_list_fields(item, keys)


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

    _coerce_list_fields(normalized)
    ensure_no_legacy_file_objects(normalized)
    return normalized


def ensure_no_legacy_file_objects(metadata: dict[str, Any]) -> None:
    """Raise when legacy file object types are present."""
    for distribution in metadata.get("distribution", []) or []:
        if distribution.get("@type") == LEGACY_FILE_OBJECT_TYPE:
            raise ValueError(
                "Legacy sc:FileObject is no longer supported. " "Please regenerate the metadata with `biotope add`."
            )


def get_status(metadata: dict[str, Any]) -> str:
    """Return the biotope pipeline state of a manifest.

    Legacy manifests (no ``biotope:status`` field) are treated as ``raw`` —
    the conservative default since nothing has explicitly declared otherwise.
    """
    value = metadata.get(STATUS)
    if value in STATUS_VALUES:
        return value
    return STATUS_RAW


def set_status(metadata: dict[str, Any], status: str) -> None:
    """Set ``biotope:status`` on a manifest. Raises ``ValueError`` on a bad value."""
    if status not in STATUS_VALUES:
        msg = f"invalid status {status!r}; expected one of {STATUS_VALUES}"
        raise ValueError(msg)
    metadata[STATUS] = status


def classify_status_from_baker(metadata: dict[str, Any]) -> str:
    """Decide raw vs. processed based on what croissant-baker produced.

    A manifest is *processed* when it has at least one ``recordSet`` entry
    with a non-empty ``field`` list — i.e. the dataset's schema is concrete
    enough for downstream mapping. Anything else (PDF, opaque blob, URL)
    stays *raw*.
    """
    for record_set in metadata.get("recordSet", []) or []:
        fields = record_set.get("field") or []
        if fields:
            return STATUS_PROCESSED
    return STATUS_RAW


def get_derived_from(metadata: dict[str, Any]) -> list[str]:
    """Return the list of ``prov:wasDerivedFrom`` source ids, if any.

    Accepts both the single-value form (``"X"`` or ``{"@id": "X"}``) and the
    list form. Returns ``[]`` when absent.
    """
    raw = metadata.get(DERIVED_FROM)
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    ids: list[str] = []
    for item in items:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict):
            value = item.get("@id")
            if isinstance(value, str):
                ids.append(value)
    return ids


def add_derived_from(metadata: dict[str, Any], source_id: str) -> None:
    """Add a ``prov:wasDerivedFrom`` pointer to ``source_id`` (idempotent)."""
    existing = get_derived_from(metadata)
    if source_id in existing:
        return
    refs = existing + [source_id]
    metadata[DERIVED_FROM] = [{"@id": ref} for ref in refs]


def resolve_content_url(content_url: str, dataset_dir: Path, biotope_root: Path) -> Path | None:
    """Resolve a ``contentUrl`` to a file on disk, or None.

    croissant-baker addresses the files it described relative to the dataset
    directory; the file objects biotope backfills are relative to the project
    root. One manifest carries both.
    """
    for candidate in (dataset_dir / content_url, biotope_root / content_url):
        if candidate.exists():
            return candidate
    return None


def names_file(distribution: dict[str, Any], dataset_dir: Path, file_path: Path, biotope_root: Path) -> bool:
    url = distribution.get("contentUrl")
    located = resolve_content_url(url, dataset_dir, biotope_root) if isinstance(url, str) else None
    return located is not None and located.resolve() == file_path.resolve()


def manifest_for(data: Path, biotope_root: Path) -> Path:
    return biotope_root / ".biotope" / "datasets" / f"{data.relative_to(biotope_root).as_posix()}.jsonld"


def dataset_id(manifest_path: Path, biotope_root: Path) -> str:
    return manifest_path.relative_to(biotope_root / ".biotope" / "datasets").as_posix().removesuffix(".jsonld")


def dataset_dir_for_manifest(manifest_path: Path, biotope_root: Path) -> Path:
    data = biotope_root / dataset_id(manifest_path, biotope_root)
    return data.parent if data.is_file() else data


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
    if not file_path.resolve().is_relative_to(biotope_root.resolve()):
        return None

    fileset_hit = False
    for distribution in metadata.get("distribution", []) or []:
        entry_type = distribution.get("@type")
        if entry_type == FILE_OBJECT_TYPE:
            if names_file(distribution, manifest_dataset_dir, file_path, biotope_root):
                return "file_object"
            continue
        if entry_type == "cr:FileSet" and not fileset_hit:
            if _fileset_covers(distribution, manifest_dataset_dir, file_path):
                fileset_hit = True

    return "fileset" if fileset_hit else None


def _fileset_covers(fileset: dict[str, Any], dataset_dir: Path, file_path: Path) -> bool:
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
    if resolved.suffix == ".jsonld":
        if not resolved.is_relative_to(biotope_root / ".biotope" / "datasets"):
            raise ValueError(f"JSON-LD target '{path}' is outside .biotope/datasets")
        return DatasetTarget(resolved, resolved, dataset_dir_for_manifest(resolved, biotope_root))
    dataset_dir = resolved if resolved.is_dir() else resolved.parent
    return DatasetTarget(resolved, manifest_for(resolved, biotope_root), dataset_dir)


def make_file_object(file_path: Path, base: Path) -> dict[str, Any]:
    relative_path = file_path.relative_to(base).as_posix()
    sha256_hash = calculate_file_checksum(file_path)
    encoding_format = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"

    return {
        "@type": FILE_OBJECT_TYPE,
        "@id": file_id(relative_path),
        "name": file_path.name,
        "contentUrl": relative_path,
        "encodingFormat": encoding_format,
        "sha256": sha256_hash,
        "contentSize": str(file_path.stat().st_size),
    }


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
