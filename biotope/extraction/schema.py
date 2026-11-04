from __future__ import annotations

import dataclasses
import types
from dataclasses import dataclass
from typing import Literal, Union, cast, get_args, get_origin, get_type_hints

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


@dataclass(frozen=True)
class Schema:
    name: str
    cls: type
    description: str
    key: tuple[str, ...]
    fields: tuple[Field, ...]

    @classmethod
    def from_class(cls, schema: object) -> Schema:
        if not isinstance(schema, type) or not dataclasses.is_dataclass(schema):
            raise ValueError(f"{schema!r}: an extraction schema must be a dataclass")
        hints = get_type_hints(schema)
        fields = tuple(
            _field(schema.__name__, item.name, hints[item.name], item.metadata.get("description", ""))
            for item in dataclasses.fields(schema)
        )
        if not fields:
            raise ValueError(f"{schema.__name__} declares no fields")
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
    def revision(self) -> str:
        fields = [dataclasses.asdict(item) for item in self.fields]
        return digest({"name": self.name, "description": self.description, "key": self.key, "fields": fields})


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
