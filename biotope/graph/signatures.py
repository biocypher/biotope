"""One resolution of authored mapping signatures, shared by checking and execution."""

from __future__ import annotations

import collections.abc
import inspect
from collections.abc import Callable
from dataclasses import dataclass, is_dataclass
from functools import lru_cache
from typing import Any, TypeVar, get_args, get_origin, get_type_hints

from biotope.graph.annotations import label, tuple_members, union_members
from biotope.graph.contracts import MappingEntry, SourceRecord
from biotope.graph.topology import CHECKABLE_TYPES, unchecked_fields


# Parameterized returns the engine can turn into an element contract.
SEQUENCES = (collections.abc.Iterable, collections.abc.Iterator, collections.abc.Generator, list)


@dataclass(frozen=True)
class Parameter:
    """One declared, evidence-bearing mapping input and the values it accepts."""

    name: str
    accepts: tuple[type, ...]


@dataclass(frozen=True)
class MappingContract:
    """Runtime contracts and report metadata derived from one authored signature."""

    name: str
    signature: inspect.Signature
    parameters: tuple[Parameter, ...]
    outputs: tuple[type, ...]
    path: str | None
    line: int | None


class SignatureError(ValueError):
    """Every independent problem found in one authored mapping signature."""

    def __init__(self, name: str, problems: tuple[tuple[str, str], ...], path: str | None, line: int | None):
        self.name = name
        self.problems = problems
        self.path = path
        self.line = line
        super().__init__("; ".join(f"{subject}: {message}" for subject, message in problems))


def _concrete(annotation: Any) -> tuple[type, ...]:
    """Require concrete dataclasses, refusing the annotations that erase contracts."""
    resolved: list[type] = []
    for member in union_members(annotation):
        # Name the annotation before narrowing, so the message reads as authored.
        authored = label(member)
        if (
            member is Any
            or member is object
            or member is SourceRecord
            or isinstance(member, TypeVar)
            or not isinstance(member, type)
            or not is_dataclass(member)
        ):
            raise ValueError(f"expected a concrete dataclass or a finite union of them, got {authored}")
        resolved.append(member)
    return tuple(dict.fromkeys(resolved))


def _input(annotation: Any) -> tuple[type, ...]:
    """Read the record types one evidence-bearing parameter accepts."""
    accepted: list[type] = []
    for member in union_members(annotation):
        if get_origin(member) is not SourceRecord:
            raise ValueError(
                f"annotate mapping inputs as SourceRecord[...] so contributors travel with them, got {label(member)}"
            )
        accepted.extend(_concrete(get_args(member)[0]))
    return tuple(dict.fromkeys(accepted))


def _outputs(annotation: Any) -> tuple[type, ...]:
    """Read the element types a mapping's return annotation produces."""
    origin, args = get_origin(annotation), get_args(annotation)
    members = tuple_members(annotation)[0] if origin is tuple else ()
    if members:
        elements = members
    elif origin in SEQUENCES and args:
        elements = (args[0],)
    else:
        raise ValueError(
            "annotate the return as a parameterized Iterable, Iterator, Generator, list or tuple of the "
            f"dataclasses the mapping produces, got {label(annotation)}"
        )
    resolved: list[type] = []
    for element in elements:
        resolved.extend(_concrete(element))
    return tuple(dict.fromkeys(resolved))


def _is_intermediate(record: type) -> bool:
    """Whether a record is neither a source record, checked with its source, nor a graph declaration."""
    return not hasattr(record, "__record_set__") and not hasattr(record, "schema_id")


def _location(function: Callable[..., object]) -> tuple[str | None, int | None]:
    """Point a reader at the authored function, when its source is available."""
    try:
        return inspect.getsourcefile(function), inspect.getsourcelines(function)[1]
    except (OSError, TypeError):
        return None, None


def _authored(entry: MappingEntry) -> Callable[..., object]:
    """Reach a registration's function for reflection only.

    ``MappingEntry`` exposes no callable member on purpose, so this internal read
    is the single place that recovers one, and it is only ever inspected here.
    Execution goes through the precisely typed ``Mapping`` object instead.
    """
    function = getattr(entry, "function", None)
    if not callable(function):
        problem = ("registration", "register a Mapping with an authored function")
        raise SignatureError(entry.name, (problem,), None, None)
    return function


@lru_cache(maxsize=None)
def contract(entry: MappingEntry) -> MappingContract:
    """Derive one registration's whole contract from its signature, once."""
    function = _authored(entry)
    path, line = _location(function)

    def reject(problems: tuple[tuple[str, str], ...]) -> SignatureError:
        return SignatureError(entry.name, problems, path, line)

    try:
        signature = inspect.signature(function)
        annotations = get_type_hints(function)
    except Exception as exc:
        raise reject((("annotations", f"could not be resolved: {exc}"),)) from exc
    problems: list[tuple[str, str]] = []
    parameters: list[Parameter] = []
    for parameter in signature.parameters.values():
        subject = f"parameter {parameter.name!r}"
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            problems.append((subject, "variadic parameters cannot carry a checked contract"))
        elif parameter.default is not parameter.empty:
            problems.append((subject, "a registered mapping takes no defaulted parameters"))
        elif parameter.name not in annotations:
            problems.append((subject, "annotate it as SourceRecord[...]"))
        else:
            try:
                parameters.append(Parameter(parameter.name, _input(annotations[parameter.name])))
            except ValueError as exc:
                problems.append((subject, str(exc)))
    if not signature.parameters:
        problems.append(("parameters", "a mapping needs at least one evidence-bearing input"))
    outputs: tuple[type, ...] = ()
    if "return" not in annotations:
        problems.append(("return", "annotate the iterable of dataclasses the mapping produces"))
    else:
        try:
            outputs = _outputs(annotations["return"])
        except ValueError as exc:
            problems.append(("return", str(exc)))
    subjects = [(f"parameter {p.name!r}", accepted) for p in parameters for accepted in p.accepts]
    for subject, record in [*subjects, *(("return", output) for output in outputs)]:
        if _is_intermediate(record):
            for problem in unchecked_fields(record):
                message = f"{problem} cannot be validated when the mapping runs; use {CHECKABLE_TYPES}"
                problems.append((subject, message))
    if problems:
        raise reject(tuple(problems))
    return MappingContract(entry.name, signature, tuple(parameters), outputs, path, line)
