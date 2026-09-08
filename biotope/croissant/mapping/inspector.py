"""Deterministic Croissant/data inspector.

This is the single source of truth for what humans and agents see about a
Croissant dataset. It surfaces record sets, fields, kinds, identifier-like
candidates and explode-eligible arrays — but it never selects
or ranks anything. Picking a record set or fields is the user's job.

Used by ``biotope map inspect``, embedded as a comment appendix in
``biotope map scaffold`` output, and consumed by the wizard.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

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
    array_shape: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "data_type": self.data_type,
            "repeated": self.repeated,
            "description": self.description,
            "is_identifier_like": self.is_identifier_like,
            "sub_fields": list(self.sub_fields),
            "array_shape": self.array_shape,
        }


@dataclass
class RecordSetInfo:
    name: str
    description: str | None
    source: str | None
    fields: list[FieldInfo] = field(default_factory=list)
    array_fields: list[str] = field(default_factory=list)
    identifier_like_fields: list[str] = field(default_factory=list)
    id: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "id": self.id,
            "description": self.description,
            "source": self.source,
            "fields": [f.to_json() for f in self.fields],
            "array_fields": list(self.array_fields),
            "identifier_like_fields": list(self.identifier_like_fields),
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
            if rs.id == name:
                return rs
        matches = [rs for rs in self.record_sets if rs.name == name]
        return matches[0] if len(matches) == 1 else None


_ID_LIKE_RE = re.compile(r"(^id$|_id$|_key$|_curie$)", re.IGNORECASE)


def inspect_dataset(
    dataset: CroissantDatasetModel,
) -> DatasetInspection:
    """Inspect ``dataset`` and return a deterministic snapshot."""
    record_sets = [_inspect_record_set(dataset, rs) for rs in dataset.record_set]
    return DatasetInspection(
        name=dataset.name,
        description=dataset.description,
        record_sets=record_sets,
    )


def _inspect_record_set(
    dataset: CroissantDatasetModel,
    rs: CroissantRecordSetModel,
) -> RecordSetInfo:
    fields = [_inspect_field(f) for f in rs.field]
    array_fields = [f.name for f in fields if f.kind == FieldKind.ARRAY.value]
    identifier_like = [f.name for f in fields if f.is_identifier_like]

    source = _resolve_source_string(dataset, rs)
    return RecordSetInfo(
        id=rs.id,
        name=rs.name,
        description=rs.description,
        source=source,
        fields=fields,
        array_fields=array_fields,
        identifier_like_fields=identifier_like,
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
        array_shape=field_model.array_shape,
    )


def _resolve_source_string(
    dataset: CroissantDatasetModel,
    rs: CroissantRecordSetModel,
) -> str | None:
    source_ids: set[str] = set()

    def collect(fields):
        for f in fields:
            if f.source:
                source_ids.update(value for value in (f.source.file_set_id, f.source.file_object_id) if value)
            collect(f.sub_field)

    collect(rs.field)
    sources = []
    for dist in dataset.distribution:
        if dist.id not in source_ids:
            continue
        if isinstance(dist, CroissantFileSetModel):
            if isinstance(dist.includes, list):
                sources.extend(dist.includes)
            else:
                sources.append(dist.includes)
        elif isinstance(dist, CroissantFileObjectModel) and dist.content_url:
            sources.append(dist.content_url)
    return ", ".join(dict.fromkeys(sources)) or None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_inspector_text(
    dataset: CroissantDatasetModel,
) -> str:
    """Plain-text inspector for embedding as a YAML comment appendix."""
    inspection = inspect_dataset(
        dataset,
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
        if rs.id:
            lines.append(f"  id (mapping record_set): {rs.id}")
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
            descr = f" — {f.description}" if f.description else ""
            if f.data_type:
                descr = f" type={f.data_type}" + descr
            if f.array_shape:
                descr = f" shape={f.array_shape}" + descr
            if f.sub_fields:
                sub = f" sub_fields=[{', '.join(f.sub_fields)}]"
                hint = (
                    f' (struct: when exploded, use field: "$item.<subfield>", '
                    f'e.g. field: "$item.{f.sub_fields[0]}"; "$<axis>.<subfield>" for multi-axis scans)'
                )
                lines.append(f"    - {f.name} [{f.kind}]{sub}{descr}{hint}")
            else:
                lines.append(f"    - {f.name} [{f.kind}]{descr}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def field_names(record_set: RecordSetInfo) -> Iterable[str]:
    return (f.name for f in record_set.fields)
