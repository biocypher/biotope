"""Deterministic Croissant/data inspector.

This is the single source of truth for what humans and agents see about a
Croissant dataset. It surfaces record sets, fields, kinds, identifier-like
candidates, explode-eligible arrays, and sample rows — but it never selects
or ranks anything. Picking a record set or fields is the user's job.

Used by ``biotope map inspect``, embedded as a comment appendix in
``biotope map scaffold`` output, and consumed by the wizard.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from biotope.croissant.acquisition.context import AcquisitionContext
from biotope.croissant.spec import (
    CroissantDatasetModel,
    CroissantFieldModel,
    CroissantFileObjectModel,
    CroissantFileSetModel,
    CroissantRecordSetModel,
    FieldKind,
)


@dataclass
class FieldInfo:
    name: str
    kind: str
    data_type: str | None
    repeated: bool
    description: str | None
    is_identifier_like: bool
    sub_fields: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "data_type": self.data_type,
            "repeated": self.repeated,
            "description": self.description,
            "is_identifier_like": self.is_identifier_like,
            "sub_fields": list(self.sub_fields),
        }


@dataclass
class RecordSetInfo:
    name: str
    description: str | None
    source: str | None
    fields: list[FieldInfo] = field(default_factory=list)
    array_fields: list[str] = field(default_factory=list)
    identifier_like_fields: list[str] = field(default_factory=list)
    sample_rows: list[dict[str, Any]] = field(default_factory=list)
    sample_note: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "fields": [f.to_json() for f in self.fields],
            "array_fields": list(self.array_fields),
            "identifier_like_fields": list(self.identifier_like_fields),
            "sample_rows": [_jsonable(row) for row in self.sample_rows],
            "sample_note": self.sample_note,
        }


@dataclass
class DatasetInspection:
    name: str | None
    description: str | None
    record_sets: list[RecordSetInfo] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "record_sets": [rs.to_json() for rs in self.record_sets],
        }

    def by_name(self, name: str) -> RecordSetInfo | None:
        for rs in self.record_sets:
            if rs.name == name:
                return rs
        return None


_ID_LIKE_RE = re.compile(r"(^id$|_id$|_key$|_curie$)", re.IGNORECASE)


def inspect_dataset(
    dataset: CroissantDatasetModel,
    *,
    datasets_location: str | Path | None = None,
    preview_rows: int = 3,
) -> DatasetInspection:
    """Inspect ``dataset`` and return a deterministic snapshot."""
    record_sets = [
        _inspect_record_set(dataset, rs, datasets_location, preview_rows)
        for rs in dataset.record_set
    ]
    return DatasetInspection(
        name=dataset.name,
        description=dataset.description,
        record_sets=record_sets,
    )


def _inspect_record_set(
    dataset: CroissantDatasetModel,
    rs: CroissantRecordSetModel,
    datasets_location: str | Path | None,
    preview_rows: int,
) -> RecordSetInfo:
    fields = [_inspect_field(f) for f in rs.field]
    array_fields = [f.name for f in fields if f.kind == FieldKind.ARRAY.value]
    identifier_like = [f.name for f in fields if f.is_identifier_like]

    source = _resolve_source_string(dataset, rs)
    sample_rows, sample_note = _read_sample_rows(
        dataset, rs, datasets_location, preview_rows
    )
    return RecordSetInfo(
        name=rs.name,
        description=rs.description,
        source=source,
        fields=fields,
        array_fields=array_fields,
        identifier_like_fields=identifier_like,
        sample_rows=sample_rows,
        sample_note=sample_note,
    )


def _inspect_field(field_model: CroissantFieldModel) -> FieldInfo:
    try:
        kind = field_model.kind().value
    except ValueError:
        kind = "unknown"
    sub_fields = [sf.name for sf in field_model.sub_field]
    return FieldInfo(
        name=field_model.name,
        kind=kind,
        data_type=field_model.data_type,
        repeated=field_model.repeated,
        description=field_model.description,
        is_identifier_like=bool(_ID_LIKE_RE.search(field_model.name)),
        sub_fields=sub_fields,
    )


def _resolve_source_string(
    dataset: CroissantDatasetModel,
    rs: CroissantRecordSetModel,
) -> str | None:
    for dist in dataset.distribution:
        if isinstance(dist, CroissantFileSetModel) and dist.id == rs.name:
            return dist.includes
        if isinstance(dist, CroissantFileObjectModel) and dist.id == rs.name:
            return dist.content_url
    return None


def _read_sample_rows(
    dataset: CroissantDatasetModel,
    rs: CroissantRecordSetModel,
    datasets_location: str | Path | None,
    preview_rows: int,
) -> tuple[list[dict[str, Any]], str | None]:
    if preview_rows <= 0:
        return [], None
    if datasets_location is None:
        return [], "data not sampled (no datasets_location provided)"
    try:
        with AcquisitionContext(
            dataset, datasets_location=datasets_location, limit=preview_rows
        ) as ctx:
            rows = list(ctx.stream(rs.name))
    except Exception as exc:  # pragma: no cover — best-effort UX
        return [], f"data not sampled ({exc})"
    return [dict(row.values) for row in rows], None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_inspector_text(
    dataset: CroissantDatasetModel,
    *,
    datasets_location: str | Path | None = None,
    preview_rows: int = 3,
) -> str:
    """Plain-text inspector for embedding as a YAML comment appendix."""
    inspection = inspect_dataset(
        dataset,
        datasets_location=datasets_location,
        preview_rows=preview_rows,
    )
    return render_inspection_text(inspection)


def render_inspection_text(inspection: DatasetInspection) -> str:
    lines: list[str] = ["Croissant inspection appendix"]
    if inspection.name:
        lines.append(f"Dataset: {inspection.name}")
    if inspection.description:
        lines.append(f"Description: {inspection.description}")
    lines.append("")

    if not inspection.record_sets:
        lines.append("No record sets declared.")
        return "\n".join(lines)

    for rs in inspection.record_sets:
        lines.append(f"Record set: {rs.name}")
        if rs.description:
            lines.append(f"  description: {rs.description}")
        if rs.source:
            lines.append(f"  source: {rs.source}")
        if rs.identifier_like_fields:
            lines.append(f"  identifier-like candidates: {', '.join(rs.identifier_like_fields)}")
        if rs.array_fields:
            lines.append(f"  explode-eligible arrays: {', '.join(rs.array_fields)}")
            lines.append(
                '    (selector for scan: {explode: <field>} is field: "$item"; '
                'multi-axis scan: {explode: {<axis>: <field>, ...}} uses field: "$<axis>")'
            )
        lines.append("  fields:")
        for f in rs.fields:
            sub = f" sub_fields=[{', '.join(f.sub_fields)}]" if f.sub_fields else ""
            descr = f" — {f.description}" if f.description else ""
            lines.append(f"    - {f.name} [{f.kind}]{sub}{descr}")
        lines.extend(_render_samples_kv(rs))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_samples_kv(rs: RecordSetInfo) -> list[str]:
    if not rs.sample_rows:
        if rs.sample_note:
            return [f"  sample rows: {rs.sample_note}"]
        return ["  sample rows: none"]

    lines = [f"  sample rows ({len(rs.sample_rows)}):"]
    for i, row in enumerate(rs.sample_rows, start=1):
        lines.append(f"    row {i}:")
        for key, value in row.items():
            lines.append(f"      {key}: {_format_value(value)}")
    return lines


def _format_value(value: Any, *, max_length: int = 80, max_items: int = 4) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return value if len(value) <= max_length else value[: max_length - 3] + "..."
    if isinstance(value, list | tuple):
        preview = [_format_value(v, max_length=max_length, max_items=max_items) for v in value[:max_items]]
        suffix = ", ..." if len(value) > max_items else ""
        return "[" + ", ".join(preview) + suffix + "]"
    if isinstance(value, dict):
        items = list(value.items())[:max_items]
        rendered = ", ".join(f"{k}: {_format_value(v, max_length=max_length)}" for k, v in items)
        suffix = ", ..." if len(value) > max_items else ""
        return "{" + rendered + suffix + "}"
    return str(value)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def field_names(record_set: RecordSetInfo) -> Iterable[str]:
    return (f.name for f in record_set.fields)
