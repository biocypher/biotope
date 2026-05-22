"""Render a typed Python schema module from a Croissant dataset.

Ported from open-targets/code_generation/schema.py; made dataset-agnostic by
removing the hard-coded ``fetch_open_targets_croissant_schema`` call and the
``OpenTargetsDatasetFieldType`` enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic.alias_generators import to_pascal, to_snake

from biotope.croissant.spec import CroissantDatasetModel, CroissantFieldModel, FieldKind


ELEMENT_FIELD_NAME = "element"
DESCRIPTION_WIDTH = 80
DOCSTRING_INDENT = 4
TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass(frozen=True)
class FieldInfo:
    """Intermediate representation of a Croissant field."""

    name: str
    description: str | None
    kind: FieldKind
    sub_fields: list[FieldInfo]
    element: FieldInfo | None = None
    parent_name: str | None = None


@dataclass(frozen=True)
class LateAttribute:
    """Class attribute deferred to after class body (avoids forward-ref issues)."""

    name: str
    type: str
    value: str


@dataclass(frozen=True)
class PrefixedClassName:
    """Helper to compose class names with stable prefixes."""

    prefix: str
    name: str

    def __str__(self) -> str:
        return f"{self.prefix}{self.name}"


@dataclass(frozen=True)
class ClassInfo:
    """One class to be emitted into the rendered module."""

    name: PrefixedClassName
    docstring_lines: list[str]
    late_attributes: list[LateAttribute]
    dependants: list[ClassInfo]
    inherit_from: str


@dataclass(frozen=True)
class FieldsHandlerResult:
    """Result bundle returned by :func:`_handle_fields`."""

    class_infos: list[ClassInfo]
    fields_attribute: LateAttribute
    field_attributes: list[LateAttribute]


def _quote(s: str) -> str:
    return f'"{s}"'


def _wrap_description(description: str | None) -> list[str]:
    if not description:
        return []
    return wrap(description, width=DESCRIPTION_WIDTH - DOCSTRING_INDENT)


def _build_docstring_lines(summary: str, description: str | None) -> list[str]:
    body = _wrap_description(description)
    return [summary] if not body else [summary, "", *body]


def _build_field_info(field: CroissantFieldModel) -> FieldInfo:
    sub = [_build_field_info(s) for s in field.sub_field]
    if field.repeated:
        if sub:
            element = FieldInfo(
                name=ELEMENT_FIELD_NAME,
                description=None,
                kind=FieldKind.STRUCT,
                sub_fields=sub,
                parent_name=field.name,
            )
        else:
            element = FieldInfo(
                name=ELEMENT_FIELD_NAME,
                description=None,
                kind=_scalar_kind(field),
                sub_fields=[],
                parent_name=field.name,
            )
        return FieldInfo(
            name=field.name,
            description=field.description,
            kind=FieldKind.ARRAY,
            sub_fields=[],
            element=element,
        )
    if sub:
        return FieldInfo(
            name=field.name,
            description=field.description,
            kind=FieldKind.STRUCT,
            sub_fields=sub,
        )
    return FieldInfo(
        name=field.name,
        description=field.description,
        kind=field.kind(),
        sub_fields=[],
    )


def _scalar_kind(field: CroissantFieldModel) -> FieldKind:
    from biotope.croissant.spec import SCALAR_KIND_MAP

    if field.data_type is None:
        msg = f"Repeated scalar field {field.name!r} has no dataType"
        raise ValueError(msg)
    if field.data_type not in SCALAR_KIND_MAP:
        msg = f"Unsupported Croissant dataType: {field.data_type!r}"
        raise ValueError(msg)
    return SCALAR_KIND_MAP[field.data_type]


def _handle_fields(
    fields: list[FieldInfo],
    owner_path: list[PrefixedClassName],
    dataset_id: str,
) -> FieldsHandlerResult:
    class_infos: list[ClassInfo] = []
    field_attrs: list[LateAttribute] = []

    for field in fields:
        info = _field_class_info(field, owner_path, dataset_id)
        class_infos.append(info)
        field_attrs.append(
            LateAttribute(
                name=f"f_{to_snake(field.name)}",
                type=f"Final[type[{_quote(str(info.name))}]]",
                value=str(info.name),
            ),
        )

    class_infos.sort(key=lambda i: str(i.name))
    fields_attr = LateAttribute(
        name="fields",
        type="Final[Sequence[type[Field]]]",
        value=f"[{', '.join(str(i.name) for i in class_infos)}]",
    )
    field_attrs.sort(key=lambda i: i.name)
    return FieldsHandlerResult(class_infos, fields_attr, field_attrs)


def _field_class_info(
    field: FieldInfo,
    owner_path: list[PrefixedClassName],
    dataset_id: str,
) -> ClassInfo:
    dataset_class_name = owner_path[0]
    owner = owner_path[-1]
    normalised = to_pascal(to_snake(field.name))
    field_class_name = PrefixedClassName("Field", owner.name + normalised)
    field_path = [*owner_path, field_class_name]
    is_array_element = field.name == ELEMENT_FIELD_NAME
    summary = (
        f"Array element of `{field.parent_name}` in dataset `{dataset_id}`."
        if is_array_element and field.parent_name is not None
        else f"Field `{field.name}` in dataset `{dataset_id}`."
    )

    attrs: list[LateAttribute] = [
        LateAttribute("name", "Final[str]", _quote(field.name)),
        LateAttribute("kind", "Final[FieldKind]", f"FieldKind.{field.kind.name}"),
        LateAttribute("dataset", "Final[type[Dataset]]", str(dataset_class_name)),
        LateAttribute(
            "path",
            "Final[Sequence[type[Dataset] | type[Field]]]",
            f"[{', '.join(str(i) for i in field_path)}]",
        ),
    ]

    dependants: list[ClassInfo] = []
    if field.kind == FieldKind.STRUCT:
        result = _handle_fields(field.sub_fields, field_path, dataset_id)
        dependants.extend(result.class_infos)
        attrs.append(result.fields_attribute)
        attrs.extend(result.field_attributes)
        inherit = "StructField"
    elif field.kind == FieldKind.ARRAY:
        if field.element is None:
            msg = f"Array field {field.name!r} has no element"
            raise ValueError(msg)
        element_info = _field_class_info(field.element, field_path, dataset_id)
        dependants.append(element_info)
        attrs.append(
            LateAttribute(
                name="element",
                type=f"Final[type[{_quote(str(element_info.name))}]]",
                value=str(element_info.name),
            ),
        )
        inherit = "SequenceField"
    else:
        inherit = "ScalarField"

    return ClassInfo(
        name=field_class_name,
        docstring_lines=_build_docstring_lines(summary, field.description),
        late_attributes=attrs,
        dependants=dependants,
        inherit_from=inherit,
    )


def _flatten(class_infos: list[ClassInfo]) -> list[ClassInfo]:
    flat: list[ClassInfo] = []

    def visit(info: ClassInfo) -> None:
        flat.append(info)
        for dep in sorted(info.dependants, key=lambda i: str(i.name)):
            visit(dep)

    for info in sorted(class_infos, key=lambda i: str(i.name)):
        visit(info)
    return flat


def _build_render_context(dataset: CroissantDatasetModel) -> dict[str, Any]:
    class_infos: list[ClassInfo] = []
    for rs in dataset.record_set:
        dataset_class_name = PrefixedClassName("Dataset", to_pascal(to_snake(rs.name)))
        attributes: list[LateAttribute] = [
            LateAttribute(name="id", type="Final[str]", value=_quote(rs.name)),
        ]
        dependants: list[ClassInfo] = []

        fields = [_build_field_info(f) for f in rs.field]
        result = _handle_fields(fields, [dataset_class_name], rs.name)
        dependants.extend(result.class_infos)
        attributes.append(result.fields_attribute)
        attributes.extend(result.field_attributes)

        class_infos.append(
            ClassInfo(
                name=dataset_class_name,
                docstring_lines=_build_docstring_lines(
                    summary=f"Dataset `{rs.name}`.",
                    description=rs.description,
                ),
                late_attributes=attributes,
                dependants=dependants,
                inherit_from="Dataset",
            ),
        )

    return {"class_infos": _flatten(class_infos)}


def render_schema_module(dataset: CroissantDatasetModel) -> str:
    """Render the typed Python module for ``dataset`` as a string."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(disabled_extensions=("jinja",)),
        keep_trailing_newline=True,
    )
    template = env.get_template("schema.py.jinja")
    return template.render(_build_render_context(dataset))
