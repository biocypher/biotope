"""The annotation vocabulary shared by schema checks, runtime validation and mapping signatures."""

from __future__ import annotations

import types
from dataclasses import is_dataclass
from typing import Any, Union, get_args, get_origin


def unwrap(annotation: Any) -> Any:
    """Return the type a ``NewType`` stands for, through any number of them."""
    while hasattr(annotation, "__supertype__"):
        annotation = annotation.__supertype__
    return annotation


def union_members(annotation: Any) -> tuple[Any, ...]:
    """Flatten a union; every other annotation is its own single member."""
    if get_origin(annotation) in (Union, types.UnionType):
        return get_args(annotation)
    return (annotation,)


def tuple_members(annotation: Any) -> tuple[tuple[Any, ...], bool]:
    """Return a tuple annotation's member types, and whether its one member repeats (``tuple[X, ...]``)."""
    args = get_args(annotation)
    if len(args) == 2 and args[1] is Ellipsis:
        return (args[0],), True
    # Python 3.10 spells ``tuple[()]`` with the arguments ``((),)``, later versions with ``()``.
    return (() if args in ((), ((),)) else args), False


def nested_records(annotation: Any) -> list[type]:
    """Return the dataclasses an annotation can hold, through unions and containers."""
    if isinstance(annotation, type) and is_dataclass(annotation):
        return [annotation]
    return [record for argument in get_args(annotation) for record in nested_records(argument)]


def contains(annotation: Any, target: object) -> bool:
    """Whether ``target`` appears anywhere in an annotation."""
    return annotation is target or any(contains(argument, target) for argument in get_args(annotation))


def is_string(annotation: Any) -> bool:
    """Whether an annotation holds one string or None: ``str``, a ``NewType`` of it, or ``str | None``."""
    members = [unwrap(member) for member in union_members(annotation)]
    return str in members and all(member in (str, type(None)) for member in members)


def label(annotation: object) -> str:
    """Name an annotation the way its author is likely to recognize it."""
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation).replace("typing.", "")
