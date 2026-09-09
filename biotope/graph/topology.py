"""Ordinary dataclasses as graph topology, with explicit semantic identities."""

from __future__ import annotations

import math
import re
import types
from dataclasses import dataclass, fields, is_dataclass
from functools import lru_cache
from typing import Any, Literal, TypedDict, Union, cast, get_args, get_origin, get_type_hints

from biotope.graph.sources import UnknownValue


@lru_cache(maxsize=None)
def hints(cls: type) -> dict[str, Any]:
    """Resolve annotations once per declaration class."""
    return get_type_hints(cls)


def identifier(value: object) -> str:
    """Require an explicit namespace, without claiming biological equivalence."""
    if not isinstance(value, str) or not re.fullmatch(r"[^\s:]+:[^\s]+", value):
        raise ValueError(f"Invalid identifier {value!r}; mint an explicit namespace:local-id in project code")
    return value


def validate_value(value: object, expected: Any, location: str) -> None:
    """Validate declarations without coercing source or scientific values."""
    if hasattr(expected, "__supertype__"):
        validate_value(value, expected.__supertype__, location)
        return
    origin, args = get_origin(expected), get_args(expected)
    if origin in (types.UnionType, Union):
        for choice in args:
            try:
                validate_value(value, choice, location)
                return
            except ValueError:
                pass
        raise ValueError(f"{location}: {value!r} does not satisfy {expected}")
    if expected is type(None) and value is None:
        return
    if expected in (str, int, float, bool) and type(value) is expected:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{location}: non-finite values are unsupported")
        return
    if origin is list and type(value) is list:
        for i, item in enumerate(cast(list[object], value)):
            validate_value(item, args[0], f"{location}[{i}]")
        return
    if isinstance(expected, type) and is_dataclass(expected) and type(value) is expected:
        for member in fields(expected):
            validate_value(getattr(value, member.name), hints(expected)[member.name], f"{location}.{member.name}")
        return
    if expected is UnknownValue:
        raise ValueError(f"{location}: unsupported source shape; refine curated metadata before loading this value")
    raise ValueError(f"{location}: expected {expected}, got {type(value).__name__}: {value!r}")


def property_type(annotation: Any) -> str:
    """Return a supported export type, rejecting implicit string conversions."""
    if hasattr(annotation, "__supertype__"):
        return property_type(annotation.__supertype__)
    if get_origin(annotation) in (Union, types.UnionType):
        nonnull = [item for item in get_args(annotation) if item is not type(None)]
        if len(nonnull) == 1:
            return property_type(nonnull[0])
    if annotation in (str, bool, int, float):
        return {str: "str", bool: "bool", int: "int", float: "float"}[annotation]
    # Lists containing nulls have no unambiguous BioCypher export representation.
    if get_origin(annotation) is list and get_args(annotation)[0] is str:
        return property_type(get_args(annotation)[0]) + "[]"
    raise ValueError(
        f"Unsupported graph/export property type {annotation}; convert it explicitly in the project mapping"
    )


def concept_id(cls: type) -> str:
    """Read a semantic identifier independent of Python module and class names."""
    value = getattr(cls, "schema_id", None)
    return identifier(value)


class ConceptSchema(TypedDict):
    """Serialized semantic topology; endpoints are present only for edges."""

    kind: Literal["node", "edge"]
    properties: dict[str, str]
    nullable: list[str]
    source: str | None
    target: str | None


@dataclass(frozen=True)
class Topology:
    """Explicit node and edge registrations; endpoint NewTypes link their contracts."""

    nodes: tuple[type, ...]
    edges: tuple[type, ...] = ()

    def describe(self) -> dict[str, ConceptSchema]:
        """Derive semantic schema and validate identifiers, endpoints and properties."""
        result: dict[str, ConceptSchema] = {}
        ids: dict[object, str] = {}
        for node in self.nodes:
            if not is_dataclass(node):
                raise ValueError(f"{node}: topology nodes must be dataclasses")
            semantic = concept_id(node)
            identity = hints(node).get("id")
            if getattr(identity, "__supertype__", None) is not str:
                raise ValueError(f"{semantic}: id must use its own NewType over str")
            if identity in ids:
                raise ValueError(f"duplicate identifier type {identity}: each node concept needs its own NewType")
            ids[identity] = semantic
        for cls in (*self.nodes, *self.edges):
            if not is_dataclass(cls):
                raise ValueError(f"{cls}: graph declarations must be dataclasses")
            semantic = concept_id(cls)
            if semantic in result:
                raise ValueError(f"duplicate concept ID {semantic}")
            names = {member.name for member in fields(cls)}
            edge = cls in self.edges
            required = {"source", "target"} if edge else {"id"}
            if not required <= names:
                raise ValueError(f"{semantic}: missing fields {sorted(required - names)}")
            annotations = hints(cls)
            item: ConceptSchema = {
                "kind": "edge" if edge else "node",
                "properties": {},
                "nullable": [],
                "source": None,
                "target": None,
            }
            if edge:
                for endpoint in ("source", "target"):
                    if annotations[endpoint] not in ids:
                        raise ValueError(
                            f"{semantic}.{endpoint}: endpoint must use a registered node's identifier NewType"
                        )
                    item[endpoint] = ids[annotations[endpoint]]
                if "id" in names and property_type(annotations["id"]) != "str":
                    raise ValueError(f"{semantic}.id must be a string identifier")
            item["properties"] = {
                member.name: property_type(annotations[member.name])
                for member in fields(cls)
                if member.name not in required | {"id"}
            }
            # Nullability is semantic too: preserve it in the topology revision.
            item["nullable"] = sorted(name for name in item["properties"] if type(None) in get_args(annotations[name]))
            result[semantic] = item
        return dict(sorted(result.items()))
