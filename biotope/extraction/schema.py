from __future__ import annotations

import dataclasses
import types
from dataclasses import dataclass
from typing import Any, Literal, Union, cast, get_args, get_origin, get_type_hints

from biotope.extraction.loading import load_object
from biotope.graph.sources import digest


JSON_TYPES: dict[object, str] = {str: "string", int: "integer", float: "number", bool: "boolean"}
ALLOWED = "str, int, float, bool, a Literal of these, a list of one of them, or one of them | None"


@dataclass(frozen=True)
class Field:
    name: str
    description: str
    type: str
    choices: tuple[object, ...] | None
    nullable: bool = False
    many: bool = False

    def value_schema(self) -> dict[str, Any]:
        nullable = self.nullable and not self.many
        schema: dict[str, Any] = {"type": [self.type, "null"] if nullable else self.type}
        if self.choices is not None:
            schema["enum"] = [*self.choices, None] if nullable else list(self.choices)
        return schema

    def json_schema(self) -> dict[str, Any]:
        if self.many:
            return {"type": "array", "description": self.description, "items": self.value_schema()}
        return {**self.value_schema(), "description": self.description}


@dataclass(frozen=True)
class Schema:
    name: str
    cls: type
    description: str
    key: tuple[str, ...]
    fields: tuple[Field, ...]

    @classmethod
    def load(cls, reference: str, root: Any = None) -> Schema:
        return cls.from_class(load_object(reference, root))

    @classmethod
    def from_class(cls, schema: object) -> Schema:
        if not isinstance(schema, type) or not dataclasses.is_dataclass(schema):
            raise ValueError(f"{schema!r}: an extraction schema must be a dataclass")
        hints = get_type_hints(schema)
        fields = tuple(
            _field(schema.__name__, item.name, hints[item.name], item.metadata.get("description", ""))
            for item in dataclasses.fields(schema)
        )
        names = {item.name: item for item in fields}
        key = tuple(cast(tuple[str, ...], getattr(schema, "__record_key__", ())))
        for name in key:
            if name not in names:
                raise ValueError(f"{schema.__name__}.__record_key__ names {name!r}, which is not a field")
            if names[name].many:
                raise ValueError(f"{schema.__name__}.{name}: a record key field cannot be a list")
        doc = schema.__doc__ or ""
        description = "" if doc.startswith(schema.__name__ + "(") else " ".join(doc.split())
        return cls(schema.__name__, schema, description, key, fields)

    @property
    def records_description(self) -> str:
        if self.key:
            return f"Every {self.name} record the document states, one per distinct {', '.join(self.key)}."
        return f"The document's {self.name} record: at most one, none when the document states none."

    def json_schema(self) -> dict[str, Any]:
        return self.wrap({item.name: item.json_schema() for item in self.fields})

    def wrap(self, properties: dict[str, Any]) -> dict[str, Any]:
        records = {"type": "array", "description": self.records_description, "items": self.record(properties)}
        return answer({"records": records})

    def record(self, properties: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "description": self.description,
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    @property
    def revision(self) -> str:
        return digest(self.json_schema())


def answer(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _field(owner: str, name: str, annotation: object, description: object) -> Field:
    refusal = ValueError(f"{owner}.{name}: {_label(annotation)} cannot be extracted; use {ALLOWED}")
    text = " ".join(str(description).split())
    origin = get_origin(annotation)
    if origin is list:
        return Field(name, text, *_scalar(get_args(annotation)[0], refusal), many=True)
    if origin in (Union, types.UnionType):
        members = [member for member in get_args(annotation) if member is not type(None)]
        if len(members) != 1 or get_origin(members[0]) is list:
            raise refusal
        return Field(name, text, *_scalar(members[0], refusal), nullable=True)
    return Field(name, text, *_scalar(annotation, refusal))


def _scalar(annotation: object, refusal: ValueError) -> tuple[str, tuple[object, ...] | None]:
    if annotation in JSON_TYPES:
        return JSON_TYPES[annotation], None
    if get_origin(annotation) is Literal:
        choices = get_args(annotation)
        kinds = {JSON_TYPES.get(type(cast(object, choice))) for choice in choices}
        if len(kinds) == 1 and None not in kinds:
            return cast(str, kinds.pop()), choices
    raise refusal


def _label(annotation: object) -> str:
    return annotation.__name__ if isinstance(annotation, type) else str(annotation).replace("typing.", "")
