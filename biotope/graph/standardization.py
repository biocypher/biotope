"""Declarative field semantics and checks; physical decoding belongs to projects."""

from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
from functools import lru_cache
from typing import Any, cast, get_args, get_type_hints


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


def field_bindings(record: type) -> dict[str, str]:
    """Derive bindings once from field declarations, including unchanged names."""
    legacy = getattr(record, "__field_refs__", None)
    if legacy is not None:
        if any("source" in member.metadata for member in fields(record)):
            raise ValueError(f"{record.__name__}: use field metadata or __field_refs__, not both")
        if not isinstance(legacy, dict):
            raise ValueError(f"{record.__name__}: invalid __field_refs__")
        return cast(dict[str, str], legacy)
    identity = getattr(record, "__record_set__", "")
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
    """Read source-local encodings without copying them into a second declaration."""
    aliases = dict(getattr(record, "__value_aliases__", {}))
    for member in fields(record):
        if member.metadata.get("aliases") is not None:
            if member.name in aliases:
                raise ValueError(f"{record.__name__}.{member.name}: aliases declared twice")
            aliases[member.name] = member.metadata["aliases"]
    return aliases


def describe_standardization(terms: tuple[Term, ...], records: tuple[type, ...]) -> dict[str, Any]:
    """Validate semantic declarations and derive a central, source-qualified overview."""
    known: dict[str, Term] = {}
    overview: dict[str, Any] = {}
    preserved: list[dict[str, Any]] = []
    for term in terms:
        if not term.standard_name.isidentifier() or not term.description.strip() or term.standard_name in known:
            raise ValueError(f"Invalid or duplicate standard term {term.standard_name!r}")
        if term.values is not None and (
            not term.values
            or len(set(term.values)) != len(term.values)
            or any(not isinstance(value, str) or not value for value in cast(tuple[object, ...], term.values))
        ):
            raise ValueError(f"{term.standard_name}: values must be distinct, nonempty strings")
        known[term.standard_name] = term
        overview[term.standard_name] = {"description": term.description, "values": term.values, "bindings": []}
    for record in records:
        if getattr(record, "__file_object__", None):
            continue
        bindings = field_bindings(record)
        annotations = get_type_hints(record)
        default_missing = getattr(record, "__missing_values__", frozenset({""}))
        for member in fields(record):
            missing = member.metadata.get("missing")
            missing = default_missing if missing is None else missing
            if not isinstance(missing, frozenset) or any(
                not isinstance(token, str) or token != token.strip().lower()
                for token in cast(frozenset[object], missing)
            ):
                raise ValueError(f"{record.__name__}.{member.name}: invalid missing-value tokens")
            missing = cast(frozenset[str], missing)
            entry: dict[str, Any] = {
                "record_set": getattr(record, "__record_set__"),
                "attribute": member.name,
                "source_field": bindings.get(member.name),
                "missing_values": sorted(missing),
                "aliases": field_aliases(record).get(member.name, {}),
            }
            term = member.metadata.get("term")
            if term is None:
                preserved.append(entry)
                continue
            if not isinstance(term, Term) or known.get(term.standard_name) != term:
                raise ValueError(f"{record.__name__}.{member.name}: unknown or conflicting standard term {term!r}")
            if member.name != term.standard_name:
                raise ValueError(f"{record.__name__}.{member.name}: standard name must be {term.standard_name}")
            if term.values is not None:
                annotation = annotations[member.name]
                members = get_args(annotation) or (annotation,)
                if str not in members or any(item not in (str, type(None)) for item in members):
                    raise ValueError(f"{record.__name__}.{member.name}: vocabulary requires str or str | None")
                if any(value not in term.values for value in entry["aliases"].values()):
                    raise ValueError(f"{record.__name__}.{member.name}: alias output is outside {term.standard_name}")
            overview[term.standard_name]["bindings"].append(entry)
    return {"terms": overview, "preserved_fields": preserved}


@lru_cache(maxsize=None)
def _vocabularies(record: type) -> tuple[tuple[str, Term], ...]:
    return tuple(
        (member.name, term)
        for member in fields(record)
        if isinstance(term := member.metadata.get("term"), Term) and term.values is not None
    )


def validate_terms(value: object) -> None:
    """Check closed vocabularies on loaded records; never parse or rewrite values."""
    for name, term in _vocabularies(type(value)):
        actual = getattr(value, name)
        if actual is not None and actual not in (term.values or ()):
            raise ValueError(f"{type(value).__name__}.{name}: {actual!r} is outside {term.standard_name}")
