"""Preview engine: validate a (partial) mapping and project its outputs.

Reused by ``biotope map preview`` and the wizard. The preview engine never
crashes on partial input; unresolved sections are reported, not fatal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from biotope.croissant.acquisition.context import AcquisitionContext
from biotope.croissant.mapping.compile import (
    iter_entity_tuples,
    iter_relation_tuples,
)
from biotope.croissant.mapping.inspector import DatasetInspection, inspect_dataset
from biotope.croissant.mapping.model import (
    EntityMapping,
    ExplodeScan,
    Mapping,
    RelationMapping,
    Selector,
    to_sentence_case,
)
from biotope.croissant.spec import CroissantDatasetModel, FieldKind


@dataclass
class ValidationFinding:
    severity: str
    path: str
    message: str

    def to_json(self) -> dict[str, Any]:
        return {"severity": self.severity, "path": self.path, "message": self.message}


@dataclass
class EntityProjection:
    key: str
    schema_term: str
    input_label: str
    namespace: str
    properties: dict[str, str]

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "schema_term": self.schema_term,
            "input_label": self.input_label,
            "namespace": self.namespace,
            "represented_as": "node",
            "properties": dict(self.properties),
        }


@dataclass
class RelationProjection:
    key: str
    schema_term: str
    input_label: str
    source: str
    target: str
    source_entity_key: str
    target_entity_key: str
    properties: dict[str, str]

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "schema_term": self.schema_term,
            "input_label": self.input_label,
            "source": self.source,
            "target": self.target,
            "source_entity_key": self.source_entity_key,
            "target_entity_key": self.target_entity_key,
            "represented_as": "edge",
            "properties": dict(self.properties),
        }


@dataclass
class MappingPreview:
    resolved_slots: list[str] = field(default_factory=list)
    unresolved_slots: list[str] = field(default_factory=list)
    findings: list[ValidationFinding] = field(default_factory=list)
    entities: list[EntityProjection] = field(default_factory=list)
    relations: list[RelationProjection] = field(default_factory=list)
    sample_node_tuples: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    # BioCypher 5-tuple: (relationship_id_or_None, source_id, target_id, label, properties).
    sample_edge_tuples: list[tuple[str | None, str, str, str, dict[str, Any]]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "resolved_slots": list(self.resolved_slots),
            "unresolved_slots": list(self.unresolved_slots),
            "findings": [f.to_json() for f in self.findings],
            "schema": {
                "entities": [e.to_json() for e in self.entities],
                "relations": [r.to_json() for r in self.relations],
            },
            "samples": {
                "nodes": [list(t[:2]) + [t[2]] for t in self.sample_node_tuples],
                "edges": [list(t) for t in self.sample_edge_tuples],
            },
        }


@dataclass
class AggregatedEntity:
    """Entity merged across all mapping files that project it."""

    key: str
    schema_term: str
    namespace: str
    properties: dict[str, str]
    sources: list[str]  # mapping file names that contributed

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "schema_term": self.schema_term,
            "namespace": self.namespace,
            "properties": dict(self.properties),
            "sources": list(self.sources),
        }


@dataclass
class AggregatedRelation:
    """Relation merged across all mapping files that project it."""

    key: str
    schema_term: str
    source_entity_key: str
    target_entity_key: str
    properties: dict[str, str]
    sources: list[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "schema_term": self.schema_term,
            "source_entity_key": self.source_entity_key,
            "target_entity_key": self.target_entity_key,
            "properties": dict(self.properties),
            "sources": list(self.sources),
        }


@dataclass
class MultiMappingPreview:
    """Project-level aggregation of multiple per-file ``MappingPreview`` objects.

    Builds the actual KG schema topology (entity → relation → entity), plus a
    slot-resolution index that records which mapping file (if any) resolves
    each slot. Conflicts in schema_term, namespace, or property types across
    files are reported as findings.
    """

    entities: list[AggregatedEntity] = field(default_factory=list)
    relations: list[AggregatedRelation] = field(default_factory=list)
    # slot_path -> [mapping file names that resolve it]
    slot_resolution: dict[str, list[str]] = field(default_factory=dict)
    # slot_path -> [mapping file names that have a non-empty but unresolved stub]
    slot_unresolved: dict[str, list[str]] = field(default_factory=dict)
    findings: list[ValidationFinding] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": {
                "entities": [e.to_json() for e in self.entities],
                "relations": [r.to_json() for r in self.relations],
            },
            "slot_resolution": {k: list(v) for k, v in self.slot_resolution.items()},
            "slot_unresolved": {k: list(v) for k, v in self.slot_unresolved.items()},
            "findings": [f.to_json() for f in self.findings],
        }


def aggregate_previews(previews: list[tuple[str, MappingPreview]]) -> MultiMappingPreview:
    """Merge a list of (file_name, MappingPreview) pairs into a project-level view.

    Entities and relations are merged by ``key``. Mismatched ``schema_term``,
    ``namespace``, endpoint, or property types across files are recorded as
    findings, but the first-seen value wins so the topology still renders.
    """
    agg = MultiMappingPreview()
    entity_by_key: dict[str, AggregatedEntity] = {}
    relation_by_key: dict[str, AggregatedRelation] = {}

    for file_name, prev in previews:
        for slot in prev.resolved_slots:
            agg.slot_resolution.setdefault(slot, []).append(file_name)
        for slot in prev.unresolved_slots:
            agg.slot_unresolved.setdefault(slot, []).append(file_name)

        for e in prev.entities:
            existing = entity_by_key.get(e.key)
            if existing is None:
                entity_by_key[e.key] = AggregatedEntity(
                    key=e.key,
                    schema_term=e.schema_term,
                    namespace=e.namespace,
                    properties=dict(e.properties),
                    sources=[file_name],
                )
                continue
            existing.sources.append(file_name)
            if existing.schema_term != e.schema_term:
                agg.findings.append(
                    ValidationFinding(
                        "warning",
                        f"entities.{e.key}",
                        f"schema_term disagrees: {existing.schema_term!r} (from {existing.sources[0]}) "
                        f"vs {e.schema_term!r} (from {file_name})",
                    )
                )
            if existing.namespace != e.namespace:
                agg.findings.append(
                    ValidationFinding(
                        "warning",
                        f"entities.{e.key}",
                        f"namespace disagrees: {existing.namespace!r} (from {existing.sources[0]}) "
                        f"vs {e.namespace!r} (from {file_name})",
                    )
                )
            for prop_name, prop_type in e.properties.items():
                if prop_name in existing.properties and existing.properties[prop_name] != prop_type:
                    agg.findings.append(
                        ValidationFinding(
                            "warning",
                            f"entities.{e.key}.properties.{prop_name}",
                            f"property type disagrees: {existing.properties[prop_name]!r} "
                            f"vs {prop_type!r} (from {file_name})",
                        )
                    )
                else:
                    existing.properties.setdefault(prop_name, prop_type)

        for r in prev.relations:
            existing = relation_by_key.get(r.key)
            if existing is None:
                relation_by_key[r.key] = AggregatedRelation(
                    key=r.key,
                    schema_term=r.schema_term,
                    source_entity_key=r.source_entity_key,
                    target_entity_key=r.target_entity_key,
                    properties=dict(r.properties),
                    sources=[file_name],
                )
                continue
            existing.sources.append(file_name)
            if existing.schema_term != r.schema_term:
                agg.findings.append(
                    ValidationFinding(
                        "warning",
                        f"relations.{r.key}",
                        f"schema_term disagrees: {existing.schema_term!r} (from {existing.sources[0]}) "
                        f"vs {r.schema_term!r} (from {file_name})",
                    )
                )
            if (existing.source_entity_key, existing.target_entity_key) != (
                r.source_entity_key,
                r.target_entity_key,
            ):
                agg.findings.append(
                    ValidationFinding(
                        "warning",
                        f"relations.{r.key}",
                        f"endpoints disagree: {existing.source_entity_key}->{existing.target_entity_key} "
                        f"(from {existing.sources[0]}) vs "
                        f"{r.source_entity_key}->{r.target_entity_key} (from {file_name})",
                    )
                )
            for prop_name, prop_type in r.properties.items():
                if prop_name in existing.properties and existing.properties[prop_name] != prop_type:
                    agg.findings.append(
                        ValidationFinding(
                            "warning",
                            f"relations.{r.key}.properties.{prop_name}",
                            f"property type disagrees: {existing.properties[prop_name]!r} "
                            f"vs {prop_type!r} (from {file_name})",
                        )
                    )
                else:
                    existing.properties.setdefault(prop_name, prop_type)

    for slot, files in agg.slot_resolution.items():
        if len(files) > 1:
            agg.findings.append(
                ValidationFinding(
                    "warning",
                    slot,
                    f"resolved by multiple mappings: {', '.join(files)}",
                )
            )

    agg.entities = list(entity_by_key.values())
    agg.relations = list(relation_by_key.values())
    return agg


def preview_mapping(
    mapping: Mapping,
    dataset: CroissantDatasetModel,
    *,
    datasets_location: str | Path | None = None,
    sample_rows: int = 3,
) -> MappingPreview:
    """Validate and project ``mapping``. Tolerant of partial input."""
    inspection = inspect_dataset(dataset, datasets_location=None, preview_rows=0)

    preview = MappingPreview()
    _classify_slots(mapping, preview)
    _validate_against_dataset(mapping, inspection, preview)
    _project_schema(mapping, preview)
    if datasets_location is not None and sample_rows > 0:
        _emit_sample_tuples(mapping, dataset, datasets_location, sample_rows, preview)
    return preview


def _classify_slots(mapping: Mapping, preview: MappingPreview) -> None:
    for name, entity in mapping.entities.items():
        if entity.is_empty():
            continue
        path = f"entities.{name}"
        (preview.resolved_slots if entity.is_resolved() else preview.unresolved_slots).append(path)
    for name, relation in mapping.relations.items():
        if relation.is_empty():
            continue
        path = f"relations.{name}"
        (preview.resolved_slots if relation.is_resolved() else preview.unresolved_slots).append(path)


def _validate_against_dataset(
    mapping: Mapping,
    inspection: DatasetInspection,
    preview: MappingPreview,
) -> None:
    rs_index = {rs.name: rs for rs in inspection.record_sets}

    for name, entity in mapping.entities.items():
        if entity.is_empty():
            continue
        path = f"entities.{name}"
        if entity.record_set is None:
            preview.findings.append(ValidationFinding("warning", path, "record_set not set"))
            continue
        rs = rs_index.get(entity.record_set)
        if rs is None:
            preview.findings.append(
                ValidationFinding("error", f"{path}.record_set", f"unknown record_set {entity.record_set!r}")
            )
            continue
        field_index = {f.name: f for f in rs.fields}
        _validate_scan(entity, path, field_index, preview)
        _validate_selector(entity.id, f"{path}.id", field_index, mapping.ids, preview)
        _validate_id_not_array(entity, f"{path}.id", field_index, mapping.ids, preview)
        for prop_name, prop in entity.properties.items():
            _validate_selector(prop, f"{path}.properties.{prop_name}", field_index, mapping.ids, preview)

    for name, relation in mapping.relations.items():
        if relation.is_empty():
            continue
        path = f"relations.{name}"
        if relation.record_set is None:
            preview.findings.append(ValidationFinding("warning", path, "record_set not set"))
            continue
        rs = rs_index.get(relation.record_set)
        if rs is None:
            preview.findings.append(
                ValidationFinding("error", f"{path}.record_set", f"unknown record_set {relation.record_set!r}")
            )
            continue
        field_index = {f.name: f for f in rs.fields}
        _validate_scan(relation, path, field_index, preview)
        for side_name, endpoint in (("source", relation.source), ("target", relation.target)):
            if endpoint is None:
                preview.findings.append(ValidationFinding("warning", f"{path}.{side_name}", "endpoint not set"))
                continue
            if endpoint.entity is None:
                preview.findings.append(
                    ValidationFinding("error", f"{path}.{side_name}.entity", "endpoint entity not set")
                )
            elif endpoint.entity not in mapping.entities:
                preview.findings.append(
                    ValidationFinding(
                        "error",
                        f"{path}.{side_name}.entity",
                        f"references unknown entity {endpoint.entity!r}",
                    )
                )
            _validate_selector(endpoint.as_selector(), f"{path}.{side_name}", field_index, mapping.ids, preview)
        for prop_name, prop in relation.properties.items():
            _validate_selector(prop, f"{path}.properties.{prop_name}", field_index, mapping.ids, preview)
        if relation.source is not None and relation.target is not None:
            src_field = _selector_field(relation.source.as_selector(), mapping.ids)
            tgt_field = _selector_field(relation.target.as_selector(), mapping.ids)
            if src_field is not None and src_field == tgt_field:
                preview.findings.append(
                    ValidationFinding(
                        "warning",
                        path,
                        f"source and target resolve to the same field {src_field!r} — " "edges will be self-loops",
                    )
                )


def _validate_id_not_array(
    entity: EntityMapping,
    path: str,
    field_index: dict[str, Any],
    ids: dict[str, Selector],
    preview: MappingPreview,
) -> None:
    """Refuse an `id` selector that resolves to an array-typed field under `scan: row`.

    Array-valued IDs produce malformed literal strings like ``"['CHEMBL748', ...]"``
    when stringified. The fix is `scan: {explode: <field>}` with `id: {field: "$item"}`
    (or pick a scalar id field).
    """
    selector = entity.id
    if selector is None:
        return
    field_name = _selector_field(selector, ids)
    # `$<axis>` selectors resolve to an exploded element, not the raw array field
    # on the row — skip the array-id check for them.
    if field_name is None or field_name.startswith("$"):
        return
    info = field_index.get(field_name)
    if info is None:
        return
    if info.kind == FieldKind.ARRAY.value and not isinstance(entity.scan, ExplodeScan):
        preview.findings.append(
            ValidationFinding(
                "error",
                path,
                f"id field {field_name!r} is array-typed; either set "
                f'`scan: {{explode: {field_name}}}` and `id: {{field: "$item"}}`, '
                "or pick a scalar id field",
            )
        )


def _selector_field(selector: Selector, ids: dict[str, Selector]) -> str | None:
    """Resolve a selector to the field it ultimately reads from, following `use:`."""
    seen: set[str] = set()
    cur = selector
    while cur is not None:
        if cur.use is not None and cur.use in ids and cur.use not in seen:
            seen.add(cur.use)
            cur = ids[cur.use]
            continue
        return cur.field
    return None


def _validate_scan(
    target: EntityMapping | RelationMapping,
    path: str,
    field_index: dict[str, Any],
    preview: MappingPreview,
) -> None:
    if isinstance(target.scan, ExplodeScan):
        for axis_name, array_field in target.scan.axes.items():
            info = field_index.get(array_field)
            label = f"{path}.scan.explode" if list(target.scan.axes) == ["item"] else f"{path}.scan.explode.{axis_name}"
            if info is None:
                preview.findings.append(ValidationFinding("error", label, f"unknown field {array_field!r}"))
            elif info.kind != FieldKind.ARRAY.value:
                preview.findings.append(
                    ValidationFinding(
                        "error",
                        label,
                        f"field {array_field!r} is {info.kind!r}, not an array",
                    )
                )


def _validate_selector(
    selector: Selector | None,
    path: str,
    field_index: dict[str, Any],
    ids: dict[str, Selector],
    preview: MappingPreview,
) -> None:
    if selector is None:
        preview.findings.append(ValidationFinding("warning", path, "selector not set"))
        return
    if selector.use is not None and selector.use not in ids:
        preview.findings.append(ValidationFinding("error", f"{path}.use", f"unknown id {selector.use!r}"))
    if selector.field is not None and not selector.field.startswith("$") and selector.field not in field_index:
        preview.findings.append(
            ValidationFinding(
                "warning",
                f"{path}.field",
                f"field {selector.field!r} not declared on the chosen record set",
            )
        )


def _project_schema(mapping: Mapping, preview: MappingPreview) -> None:
    for name, entity in mapping.entities.items():
        if not entity.is_resolved():
            continue
        schema_term = entity.schema_term or to_sentence_case(name)
        namespace = entity.namespace or _derive_namespace(entity.id, mapping.ids) or "id"
        properties = {
            prop_name: _property_type(prop, entity.record_set, mapping) for prop_name, prop in entity.properties.items()
        }
        preview.entities.append(
            EntityProjection(
                key=name,
                schema_term=schema_term,
                input_label=name,
                namespace=namespace,
                properties=properties,
            )
        )

    entity_terms = {e.key: e.schema_term for e in preview.entities}
    for name, relation in mapping.relations.items():
        if not relation.is_resolved():
            continue
        schema_term = relation.schema_term or to_sentence_case(name)
        source_entity_key = relation.source.entity if relation.source else ""
        target_entity_key = relation.target.entity if relation.target else ""
        source_term = entity_terms.get(source_entity_key, source_entity_key)
        target_term = entity_terms.get(target_entity_key, target_entity_key)
        properties = {
            prop_name: _property_type(prop, relation.record_set, mapping)
            for prop_name, prop in relation.properties.items()
        }
        preview.relations.append(
            RelationProjection(
                key=name,
                schema_term=schema_term,
                input_label=name,
                source=source_term,
                target=target_term,
                source_entity_key=source_entity_key,
                target_entity_key=target_entity_key,
                properties=properties,
            )
        )


def _derive_namespace(selector: Selector | None, ids: dict[str, Selector]) -> str | None:
    if selector is None:
        return None
    if selector.use is not None and selector.use in ids:
        return _derive_namespace(ids[selector.use], ids)
    if selector.transform == "as_curie":
        prefix = selector.args.get("prefix")
        if isinstance(prefix, str):
            return prefix
    return None


def _property_type(prop: Selector, record_set: str | None, mapping: Mapping) -> str:
    if prop.use is not None:
        return "str"
    if record_set is None or prop.field is None:
        return "str"
    if prop.field.startswith("$item"):
        return "str"  # struct fields not supported in v1
    return "str"  # actual Croissant kind mapping is handled in materialize


def _emit_sample_tuples(
    mapping: Mapping,
    dataset: CroissantDatasetModel,
    datasets_location: str | Path,
    sample_rows: int,
    preview: MappingPreview,
) -> None:
    try:
        with AcquisitionContext(dataset, datasets_location=datasets_location, limit=sample_rows) as ctx:
            for tup in iter_entity_tuples(mapping, ctx, only_resolved=True):
                preview.sample_node_tuples.append(tup)
                if len(preview.sample_node_tuples) >= sample_rows * max(1, len(mapping.entities)):
                    break
        with AcquisitionContext(dataset, datasets_location=datasets_location, limit=sample_rows) as ctx:
            for tup in iter_relation_tuples(mapping, ctx, only_resolved=True):
                preview.sample_edge_tuples.append(tup)
                if len(preview.sample_edge_tuples) >= sample_rows * max(1, len(mapping.relations)):
                    break
    except Exception as exc:  # pragma: no cover — best-effort preview
        preview.findings.append(ValidationFinding("warning", "samples", f"could not stream samples: {exc}"))
