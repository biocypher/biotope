"""Declarative field semantics and checks; physical decoding belongs to projects."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import MISSING, dataclass, field, fields, is_dataclass
from functools import lru_cache
from typing import Any, cast, get_type_hints

from biotope.graph.annotations import is_string, nested_records


@dataclass(frozen=True)
class Term:
    """One shared meaning, optionally constrained to a closed vocabulary."""

    standard_name: str
    description: str
    values: tuple[str, ...] | None = None


def source_field(
    source: str | None = "",
    *,
    term: Term | None = None,
    aliases: dict[str, str] | None = None,
    missing: frozenset[str] | None = None,
    default: Any = MISSING,
) -> Any:
    """Bind a dataclass field. Empty source means its own name; None means unsupplied."""
    return field(default=default, metadata={"source": source, "term": term, "aliases": aliases, "missing": missing})


def field_bindings(record: type, scope: str = "") -> dict[str, str]:
    """Map attributes to source field identities, from field metadata or the legacy ``__field_refs__``.

    Fields bind under the record's ``__record_set__``, or under ``scope`` when it declares none.
    """
    legacy = getattr(record, "__field_refs__", None)
    if legacy is not None:
        if any("source" in member.metadata for member in fields(record)):
            raise ValueError(f"{record.__name__}: use field metadata or __field_refs__, not both")
        if not isinstance(legacy, dict):
            raise ValueError(f"{record.__name__}: invalid __field_refs__")
        return cast(dict[str, str], legacy)
    identity = getattr(record, "__record_set__", "") or scope
    bindings: dict[str, str] = {}
    for member in fields(record):
        source = member.metadata.get("source", "")
        if source is None:
            continue
        if not isinstance(source, str):
            raise ValueError(f"{record.__name__}.{member.name}: source must be a field identity or None")
        source = source or member.name
        bindings[member.name] = source if source.startswith(identity + "/") else f"{identity}/{source}"
    return bindings


def field_aliases(record: type) -> dict[str, dict[str, str]]:
    """Merge ``__value_aliases__`` with each field's ``aliases``, refusing an attribute declared in both."""
    aliases = dict(getattr(record, "__value_aliases__", {}))
    for member in fields(record):
        if member.metadata.get("aliases") is not None:
            if member.name in aliases:
                raise ValueError(f"{record.__name__}.{member.name}: aliases declared twice")
            aliases[member.name] = member.metadata["aliases"]
    return aliases


def _registry(terms: tuple[Term, ...]) -> dict[str, Term]:
    registry: dict[str, Term] = {}
    for term in terms:
        if not term.standard_name.isidentifier() or not term.description.strip() or term.standard_name in registry:
            raise ValueError(f"Invalid or duplicate standard term {term.standard_name!r}")
        if term.values is not None and (
            not term.values
            or len(set(term.values)) != len(term.values)
            or any(not isinstance(value, str) or not value for value in cast(tuple[object, ...], term.values))
        ):
            raise ValueError(f"{term.standard_name}: values must be distinct, nonempty strings")
        registry[term.standard_name] = term
    return registry


def _scoped_records(records: tuple[type, ...]) -> Iterator[tuple[type, str]]:
    """Every record with the identity its fields bind under, nested field records and document facts included.

    A nested record without its own ``__record_set__`` binds under the field that holds it.
    """
    pending = [(record, getattr(record, "__record_set__", record.__name__)) for record in records]
    seen: set[tuple[type, str]] = set()
    while pending:
        record, scope = pending.pop(0)
        if (record, scope) in seen:
            continue
        seen.add((record, scope))
        yield record, scope
        bindings, hints = field_bindings(record, scope), get_type_hints(record)
        for name in _nested_members(record):
            within = bindings.get(name, f"{scope}/{name}")
            pending += [
                (nested, getattr(nested, "__record_set__", None) or within) for nested in nested_records(hints[name])
            ]


def _field_entries(record: type, scope: str, registry: dict[str, Term]) -> Iterator[tuple[dict[str, Any], Term | None]]:
    """Each field's overview entry, with the registered term it binds to, if any."""
    bindings, aliases, hints = field_bindings(record, scope), field_aliases(record), get_type_hints(record)
    default_missing = getattr(record, "__missing_values__", frozenset({""}))
    for member in fields(record):
        missing = member.metadata.get("missing")
        missing = default_missing if missing is None else missing
        if not isinstance(missing, frozenset) or any(
            not isinstance(token, str) or token != token.strip().lower() for token in cast(frozenset[object], missing)
        ):
            raise ValueError(f"{record.__name__}.{member.name}: invalid missing-value tokens")
        entry: dict[str, Any] = {
            "record_set": scope,
            "attribute": member.name,
            "source_field": bindings.get(member.name),
            "missing_values": sorted(cast(frozenset[str], missing)),
            "aliases": aliases.get(member.name, {}),
        }
        term = member.metadata.get("term")
        if term is None:
            yield entry, None
            continue
        if not isinstance(term, Term) or registry.get(term.standard_name) != term:
            raise ValueError(f"{record.__name__}.{member.name}: unknown or conflicting standard term {term!r}")
        if member.name != term.standard_name:
            raise ValueError(f"{record.__name__}.{member.name}: standard name must be {term.standard_name}")
        if term.values is not None:
            if not is_string(hints[member.name]):
                raise ValueError(f"{record.__name__}.{member.name}: vocabulary requires str or str | None")
            if any(value not in term.values for value in entry["aliases"].values()):
                raise ValueError(f"{record.__name__}.{member.name}: alias output is outside {term.standard_name}")
        yield entry, term


def describe_standardization(terms: tuple[Term, ...], records: tuple[type, ...]) -> dict[str, Any]:
    """Validate semantic declarations and derive a central, source-qualified overview."""
    registry = _registry(terms)
    overview: dict[str, dict[str, Any]] = {
        name: {"description": term.description, "values": term.values, "bindings": []}
        for name, term in registry.items()
    }
    preserved: list[dict[str, Any]] = []
    for record, scope in _scoped_records(records):
        for entry, term in _field_entries(record, scope, registry):
            if term is None:
                preserved.append(entry)
            else:
                overview[term.standard_name]["bindings"].append(entry)
    return {"terms": overview, "preserved_fields": preserved}


@lru_cache(maxsize=None)
def _nested_members(record: type) -> tuple[str, ...]:
    """Fields of a record that hold nested field records."""
    hints = get_type_hints(record)
    return tuple(member.name for member in fields(record) if nested_records(hints[member.name]))


@lru_cache(maxsize=None)
def _vocabularies(record: type) -> tuple[tuple[str, Term], ...]:
    return tuple(
        (member.name, term)
        for member in fields(record)
        if isinstance(term := member.metadata.get("term"), Term) and term.values is not None
    )


def validate_terms(value: object, location: str = "") -> None:
    """Check closed vocabularies on loaded records, nested ones included; never parse or rewrite values."""
    record = type(value)
    prefix = location or record.__name__
    for name, term in _vocabularies(record):
        actual = getattr(value, name)
        if actual is not None and actual not in (term.values or ()):
            raise ValueError(f"{prefix}.{name}: {actual!r} is outside {term.standard_name}")
    for name in _nested_members(record):
        _validate_nested(getattr(value, name), f"{prefix}.{name}")


def _validate_nested(item: object, location: str) -> None:
    if isinstance(item, (list, tuple)):
        for index, element in enumerate(cast(list[object], item)):
            _validate_nested(element, f"{location}[{index}]")
    elif is_dataclass(item) and not isinstance(item, type):
        validate_terms(item, location)
