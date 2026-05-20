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
    sample_edge_tuples: list[tuple[str, str, str, str, dict[str, Any]]] = field(default_factory=list)

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
                "edges": [list(t[:4]) + [t[4]] for t in self.sample_edge_tuples],
            },
        }


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
        path = f"entities.{name}"
        (preview.resolved_slots if entity.is_resolved() else preview.unresolved_slots).append(path)
    for name, relation in mapping.relations.items():
        path = f"relations.{name}"
        (preview.resolved_slots if relation.is_resolved() else preview.unresolved_slots).append(path)


def _validate_against_dataset(
    mapping: Mapping,
    inspection: DatasetInspection,
    preview: MappingPreview,
) -> None:
    rs_index = {rs.name: rs for rs in inspection.record_sets}

    for name, entity in mapping.entities.items():
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
        for prop_name, prop in entity.properties.items():
            _validate_selector(prop, f"{path}.properties.{prop_name}", field_index, mapping.ids, preview)

    for name, relation in mapping.relations.items():
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
                preview.findings.append(
                    ValidationFinding("warning", f"{path}.{side_name}", "endpoint not set")
                )
                continue
            if endpoint.entity is None:
                preview.findings.append(
                    ValidationFinding(
                        "error", f"{path}.{side_name}.entity", "endpoint entity not set"
                    )
                )
            elif endpoint.entity not in mapping.entities:
                preview.findings.append(
                    ValidationFinding(
                        "error",
                        f"{path}.{side_name}.entity",
                        f"references unknown entity {endpoint.entity!r}",
                    )
                )
            _validate_selector(
                endpoint.as_selector(), f"{path}.{side_name}", field_index, mapping.ids, preview
            )
        for prop_name, prop in relation.properties.items():
            _validate_selector(
                prop, f"{path}.properties.{prop_name}", field_index, mapping.ids, preview
            )


def _validate_scan(
    target: EntityMapping | RelationMapping,
    path: str,
    field_index: dict[str, Any],
    preview: MappingPreview,
) -> None:
    if isinstance(target.scan, ExplodeScan):
        info = field_index.get(target.scan.explode)
        if info is None:
            preview.findings.append(
                ValidationFinding(
                    "error",
                    f"{path}.scan.explode",
                    f"unknown field {target.scan.explode!r}",
                )
            )
        elif info.kind != FieldKind.ARRAY.value:
            preview.findings.append(
                ValidationFinding(
                    "error",
                    f"{path}.scan.explode",
                    f"field {target.scan.explode!r} is {info.kind!r}, not an array",
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
        preview.findings.append(
            ValidationFinding("error", f"{path}.use", f"unknown id {selector.use!r}")
        )
    if (
        selector.field is not None
        and not selector.field.startswith("$item")
        and selector.field not in field_index
    ):
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
            prop_name: _property_type(prop, entity.record_set, mapping)
            for prop_name, prop in entity.properties.items()
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
        with AcquisitionContext(
            dataset, datasets_location=datasets_location, limit=sample_rows
        ) as ctx:
            for tup in iter_entity_tuples(mapping, ctx, only_resolved=True):
                preview.sample_node_tuples.append(tup)
                if len(preview.sample_node_tuples) >= sample_rows * max(1, len(mapping.entities)):
                    break
        with AcquisitionContext(
            dataset, datasets_location=datasets_location, limit=sample_rows
        ) as ctx:
            for tup in iter_relation_tuples(mapping, ctx, only_resolved=True):
                preview.sample_edge_tuples.append(tup)
                if len(preview.sample_edge_tuples) >= sample_rows * max(1, len(mapping.relations)):
                    break
    except Exception as exc:  # pragma: no cover — best-effort preview
        preview.findings.append(
            ValidationFinding("warning", "samples", f"could not stream samples: {exc}")
        )
