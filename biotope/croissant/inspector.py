"""Human and machine views of declared Croissant metadata, without payload I/O.

Inspection preserves identities and nesting. Full source contracts are generated
separately from curated metadata in ``biotope.graph.sources``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath
from typing import Any

from rich.console import Console, RenderableType
from rich.table import Table
from rich.text import Text

from biotope.croissant.spec import CroissantDatasetModel, CroissantFieldModel


@dataclass
class FieldInfo:
    id: str | None
    name: str
    kind: str
    data_type: str | None
    repeated: bool
    description: str | None
    source: dict[str, Any] | None
    sub_fields: list[FieldInfo] = field(default_factory=list)
    array_shape: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecordSetInfo:
    id: str | None
    name: str
    description: str | None
    source_ids: list[str]
    fields: list[FieldInfo] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetInspection:
    id: str | None
    name: str | None
    description: str | None
    context: Any
    distribution: list[dict[str, Any]]
    record_sets: list[RecordSetInfo] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {"schema_version": 2, **asdict(self)}

    def by_name(self, name: str) -> RecordSetInfo | None:
        for rs in self.record_sets:
            if rs.id == name:
                return rs
        matches = [rs for rs in self.record_sets if rs.name == name]
        return matches[0] if len(matches) == 1 else None


def inspect_dataset(dataset: CroissantDatasetModel) -> DatasetInspection:
    """Preserve field order, exact IDs and declared source links for both views."""
    record_sets = []
    for rs in dataset.record_set:
        source_ids: dict[str, None] = {}
        for f in _walk_fields(rs.field):
            if f.source:
                for source_id in (f.source.file_object_id, f.source.file_set_id):
                    if source_id:
                        source_ids[source_id] = None
        record_sets.append(
            RecordSetInfo(
                id=rs.id,
                name=rs.name,
                description=rs.description,
                source_ids=list(source_ids),
                fields=[_inspect_field(f) for f in rs.field],
                attributes=dict(rs.model_extra or {}),
            )
        )
    return DatasetInspection(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        context=dataset.context,
        distribution=[d.model_dump(by_alias=True, exclude_unset=True) for d in dataset.distribution],
        record_sets=record_sets,
        attributes=dict(dataset.model_extra or {}),
    )


def _walk_fields(fields: list[CroissantFieldModel]) -> Iterator[CroissantFieldModel]:
    for f in fields:
        yield f
        yield from _walk_fields(f.sub_field)


def _inspect_field(model: CroissantFieldModel) -> FieldInfo:
    try:
        kind = model.kind().value
    except ValueError:
        kind = "unknown"
    return FieldInfo(
        id=model.id,
        name=model.name,
        kind=kind,
        data_type=model.data_type,
        repeated=model.repeated,
        description=model.description,
        source=model.source.model_dump(by_alias=True, exclude_unset=True) if model.source else None,
        sub_fields=[_inspect_field(f) for f in model.sub_field],
        array_shape=model.array_shape,
        attributes=dict(model.model_extra or {}),
    )


def _grid(label_width: int = 8) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(width=label_width, min_width=label_width, max_width=label_width, overflow="fold")
    table.add_column(overflow="fold")
    return table


def _source_paths(distribution: dict[str, Any]) -> list[str]:
    value = distribution.get("contentUrl") or distribution.get("includes")
    return [value] if isinstance(value, str) else list(value or [])


def _is_redundant(description: str | None, boilerplate: list[str]) -> bool:
    # Only exact repeats are omitted. Appended parse notes remain visible.
    return description is not None and description.strip() in boilerplate


def _declared_type(f: FieldInfo) -> str:
    value = f.data_type or ("Struct" if f.sub_fields else "Not declared")
    for prefix in ("sc:", "cr:", "https://schema.org/", "http://schema.org/", "http://mlcommons.org/croissant/"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    return value + ("[]" if f.repeated else "")


def _field_rows(
    fields: list[FieldInfo],
    paths: list[str],
    record_name: str,
    prefix: str = "",
    nested: bool = False,
) -> Iterator[tuple[str, RenderableType]]:
    for index, f in enumerate(fields):
        last = index == len(fields) - 1
        branch = prefix + ("└─ " if last else "├─ ") if nested else ""
        label = Text(f.name)
        if f.array_shape:
            label.append(f"  [shape: {f.array_shape}]", style="dim")
        boilerplate = [f"Column '{f.name}'"]
        for path in paths:
            boilerplate.extend(
                [f"Column '{f.name}' from {path}", f"Column '{f.name}' of sheet '{record_name}' in {path}"]
            )
        if f.description and not _is_redundant(f.description, boilerplate):
            label.append("\n" + f.description, style="dim")
        content: RenderableType
        if branch:
            indented = Table.grid(padding=0)
            indented.add_column(width=len(branch), min_width=len(branch), max_width=len(branch))
            indented.add_column(overflow="fold")
            indented.add_row(Text(branch, style="dim"), label)
            content = indented
        else:
            content = label
        yield _declared_type(f), content
        child_prefix = prefix + ("   " if last else "│  ") if nested else ""
        yield from _field_rows(f.sub_fields, paths, record_name, child_prefix, nested=True)


def render_inspection(inspection: DatasetInspection, console: Console) -> None:
    """Show full paths and fields in wrapping blocks, grouped by source identity."""
    count = len(inspection.record_sets)
    console.print(Text(f"{inspection.name or 'Dataset'} · {count} record set{'s' if count != 1 else ''}", style="bold"))
    if inspection.description:
        console.print(Text(inspection.description))
    console.print(Text("Declared types", style="dim"))
    if not inspection.record_sets:
        console.print("\nNo record sets declared.")
        return

    distributions = {d["@id"]: d for d in inspection.distribution}
    # Group explicit shared sources (e.g. workbook sheets), never filename prefixes.
    # Unlinked record sets each get their own block.
    groups: dict[frozenset[str] | int, list[RecordSetInfo]] = {}
    for index, rs in enumerate(inspection.record_sets):
        key = frozenset(rs.source_ids) if rs.source_ids else index
        groups.setdefault(key, []).append(rs)

    for group in groups.values():
        console.print()
        paths = []
        sources = _grid()
        for source_id in group[0].source_ids:
            dist = distributions.get(source_id)
            locations = _source_paths(dist) if dist is not None else []
            paths.extend(locations)
            for location in locations or [
                f"No path declared: {source_id}" if dist is not None else f"Unresolved source: {source_id}"
            ]:
                sources.add_row(Text("SOURCE", style="bold cyan"), Text(location))
        if not group[0].source_ids:
            sources.add_row(Text("SOURCE", style="bold cyan"), Text("Not declared", style="dim"))
        console.print(sources)

        for rs in group:
            heading = _grid()
            redundant_name = len(paths) == 1 and rs.name in (paths[0], PurePosixPath(paths[0]).stem)
            if len(group) > 1 or not redundant_name:
                heading.add_row(Text("RECORD", style="bold"), Text(rs.name, style="bold"))
            if rs.description and not _is_redundant(rs.description, [f"Records from {path}" for path in paths]):
                heading.add_row(Text("NOTE", style="dim"), Text(rs.description))
            if heading.row_count:
                console.print(heading)
            console.print()
            rows = list(_field_rows(rs.fields, paths, rs.name))
            if rows:
                fields = _grid(label_width=max(8, min(14, max(len(t) for t, _ in rows))))
                for dtype, content in rows:
                    fields.add_row(Text(dtype, style="cyan"), content)
                console.print(fields)
            else:
                console.print(Text("No fields declared.", style="dim"))
            console.print()
