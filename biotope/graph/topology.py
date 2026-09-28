"""Ordinary dataclasses as graph topology, with explicit semantic identities."""

from __future__ import annotations

import inspect
import math
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields, is_dataclass
from functools import lru_cache
from itertools import repeat
from typing import Any, Literal, TypedDict, cast, get_args, get_origin, get_type_hints

from biotope.graph.annotations import label, nested_records, tuple_members, union_members, unwrap
from biotope.graph.sources import UnknownValue


# Concept IDs in this namespace are reserved for Biotope's own metadata.
RESERVED_NAMESPACE = "biotope"


@lru_cache(maxsize=None)
def hints(cls: type) -> dict[str, Any]:
    """Resolve annotations once per declaration class."""
    return get_type_hints(cls)


@lru_cache(maxsize=None)
def field_names(cls: type) -> tuple[str, ...]:
    """List a dataclass's fields once per declaration class."""
    return tuple(member.name for member in fields(cls))


IDENTIFIER = re.compile(r"[^\s:]+:[^\s]+")


def identifier(value: object) -> str:
    """Require an explicit namespace, without claiming biological equivalence."""
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid identifier {value!r}; mint an explicit namespace:local-id in project code")
    return value


def concept_description(cls: type) -> str:
    """Read an authored class description, ignoring the synthesized dataclass signature."""
    text = cls.__dict__.get("__doc__") or ""
    return "" if text.startswith(cls.__name__ + "(") else inspect.cleandoc(text)


ValueCheck = Callable[[object], "str | None"]


def validate_value(value: object, expected: Any, subject: str, evidence: object) -> None:
    """Refuse a value that departs from its declaration, naming its path; never coerce the value."""
    problem = value_check(expected)(value)
    if problem is not None:
        raise ValueError(f"{subject} {evidence}{problem}")


def first_problem(items: Iterable[object], checks: Iterable[ValueCheck]) -> str | None:
    for index, (item, check) in enumerate(zip(items, checks)):
        if (problem := check(item)) is not None:
            return f"[{index}]{problem}"
    return None


@lru_cache(maxsize=None)
def value_check(expected: Any) -> ValueCheck:
    """Resolve a declared type once into a check of its values."""
    expected = unwrap(expected)

    def mismatch(value: object) -> str:
        return f": expected {expected}, got {type(value).__name__}: {value!r}"

    choices = union_members(expected)
    if len(choices) > 1:
        alternatives = tuple(value_check(choice) for choice in choices)

        def check_union(value: object) -> str | None:
            if any(check(value) is None for check in alternatives):
                return None
            return f": {value!r} does not satisfy {expected}"

        return check_union
    if expected is float:

        def check_float(value: object) -> str | None:
            if type(value) is not float:
                return mismatch(value)
            return None if math.isfinite(value) else ": non-finite values are unsupported"

        return check_float
    if expected in (str, int, bool, type(None)):
        return lambda value: None if type(value) is expected else mismatch(value)
    origin, args = get_origin(expected), get_args(expected)
    if origin is list:
        item_check = value_check(args[0])

        def check_list(value: object) -> str | None:
            if type(value) is not list:
                return mismatch(value)
            return first_problem(cast(list[object], value), repeat(item_check))

        return check_list
    if origin is tuple:
        members, repeated = tuple_members(expected)
        slot_checks = tuple(value_check(member) for member in members)

        def check_tuple(value: object) -> str | None:
            if type(value) is not tuple:
                return mismatch(value)
            items = cast(tuple[object, ...], value)
            if repeated:
                return first_problem(items, repeat(slot_checks[0]))
            if len(slot_checks) != len(items):
                return f": expected {expected}, got {len(items)} items: {value!r}"
            return first_problem(items, slot_checks)

        return check_tuple
    if isinstance(expected, type) and is_dataclass(expected):
        record = expected
        # Resolved on first use, so a record that nests itself does not recurse while its check is built.
        field_checks: list[tuple[str, ValueCheck]] | None = None

        def check_record(value: object) -> str | None:
            nonlocal field_checks
            if type(value) is not record:
                return mismatch(value)
            if field_checks is None:
                field_checks = [(member.name, value_check(hints(record)[member.name])) for member in fields(record)]
            for name, check in field_checks:
                problem = check(getattr(value, name))
                if problem is not None:
                    return f".{name}{problem}"
            return None

        return check_record
    if expected is UnknownValue:
        return lambda value: ": unsupported source shape; refine curated metadata before loading this value"
    return mismatch


CHECKABLE_TYPES = "str, int, float, bool, None, a NewType, list[...], tuple[...] or a dataclass"


def is_checkable(annotation: Any) -> bool:
    """Whether validate_value can check values of an annotation."""
    annotation = unwrap(annotation)
    choices = union_members(annotation)
    if len(choices) > 1:
        return all(is_checkable(choice) for choice in choices)
    if annotation in (type(None), str, int, float, bool) or annotation is UnknownValue:
        return True
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is list:
        return len(args) == 1 and is_checkable(args[0])
    if origin is tuple:
        return all(is_checkable(member) for member in tuple_members(annotation)[0])
    return isinstance(annotation, type) and is_dataclass(annotation)


def unchecked_fields(record: type) -> list[str]:
    """Fields of a record, nested records included, whose declared types validate_value cannot check.

    Execution validates every value against its declaration, so an unsupported
    annotation would otherwise fail only once a build reaches the first value.
    """
    problems: list[str] = []
    pending, seen = [record], set[type]()
    while pending:
        cls = pending.pop(0)
        if cls in seen:
            continue
        seen.add(cls)
        try:
            annotations = hints(cls)
        except Exception as exc:
            problems.append(f"{cls.__name__}: annotations could not be resolved: {exc}")
            continue
        for member in fields(cls):
            annotation = annotations[member.name]
            pending.extend(nested_records(annotation))
            if not is_checkable(annotation):
                problems.append(f"{cls.__name__}.{member.name}: {label(annotation)}")
    return problems


def property_type(annotation: Any) -> str:
    """Return a supported export type, rejecting implicit string conversions."""
    annotation = unwrap(annotation)
    nonnull = [item for item in union_members(annotation) if item is not type(None)]
    if len(nonnull) == 1 and nonnull[0] is not annotation:
        return property_type(nonnull[0])
    if annotation in (str, bool, int, float):
        return {str: "str", bool: "bool", int: "int", float: "float"}[annotation]
    # Lists containing nulls have no unambiguous BioCypher export representation.
    if get_origin(annotation) is list and get_args(annotation)[0] is str:
        return property_type(get_args(annotation)[0]) + "[]"
    raise ValueError(
        f"Unsupported graph/export property type {annotation}; convert it explicitly in the project mapping"
    )


@lru_cache(maxsize=None)
def concept_id(cls: type) -> str:
    """Read a semantic identifier independent of Python module and class names."""
    value = getattr(cls, "schema_id", None)
    return identifier(value)


class ConceptDescription(TypedDict):
    """Authored meaning, kept out of the structural digest so wording can improve."""

    description: str
    properties: dict[str, str]


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
            if not bool(getattr(getattr(cls, "__dataclass_params__", None), "frozen", False)):
                raise ValueError(f"{cls}: graph declarations must be frozen dataclasses")
            semantic = concept_id(cls)
            if semantic.split(":", 1)[0] == RESERVED_NAMESPACE:
                raise ValueError(f"{semantic}: the {RESERVED_NAMESPACE}: namespace is reserved for export metadata")
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

    def descriptions(self) -> dict[str, ConceptDescription]:
        """Collect authored concept and property descriptions, separate from structure."""
        return {
            concept_id(cls): {
                "description": concept_description(cls),
                "properties": {
                    member.name: " ".join(str(member.metadata.get("description", "")).split())
                    for member in fields(cls)
                    if member.name not in (("id", "source", "target") if cls in self.edges else ("id",))
                },
            }
            for cls in sorted((*self.nodes, *self.edges), key=concept_id)
        }
