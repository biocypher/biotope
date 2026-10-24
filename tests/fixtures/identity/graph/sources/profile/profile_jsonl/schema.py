# This file is yours to edit; biotope never rewrites it. After a manifest change,
# review the drift biotope graph check explains, then update __source_digest__.
"""Typed records for one described record set; bindings name its Croissant fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class ProfileJsonlValuesNameEvidence:
    __record_set__: ClassVar[str] = "profile.jsonl/values/name/evidence"

    quote: str | None = None
    locator: str | None = None
    aligned: bool | None = None
    start: int | None = None
    end: int | None = None
    page: int | None = None
    occurrences: int | None = None
    weak: list[str | None] | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileJsonlValuesName:
    __record_set__: ClassVar[str] = "profile.jsonl/values/name"

    value: str
    evidence: ProfileJsonlValuesNameEvidence | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileJsonlValuesOrcidEvidence:
    __record_set__: ClassVar[str] = "profile.jsonl/values/orcid/evidence"

    quote: str | None = None
    locator: str | None = None
    aligned: bool | None = None
    start: int | None = None
    end: int | None = None
    page: int | None = None
    occurrences: int | None = None
    weak: list[str | None] | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileJsonlValuesOrcid:
    __record_set__: ClassVar[str] = "profile.jsonl/values/orcid"

    value: str | None = None
    evidence: ProfileJsonlValuesOrcidEvidence | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileJsonlValuesEmailsEvidence:
    __record_set__: ClassVar[str] = "profile.jsonl/values/emails/evidence"

    quote: str | None = None
    locator: str | None = None
    aligned: bool | None = None
    start: int | None = None
    end: int | None = None
    page: int | None = None
    occurrences: int | None = None
    weak: list[str | None] | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileJsonlValuesEmails:
    __record_set__: ClassVar[str] = "profile.jsonl/values/emails"

    value: str
    evidence: ProfileJsonlValuesEmailsEvidence | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileJsonlValues:
    __record_set__: ClassVar[str] = "profile.jsonl/values"

    name: ProfileJsonlValuesName
    orcid: ProfileJsonlValuesOrcid
    emails: list[ProfileJsonlValuesEmails | None]


@dataclass(frozen=True, kw_only=True)
class ProfileJsonlProvenanceExtractor:
    __record_set__: ClassVar[str] = "profile.jsonl/provenance/extractor"

    name: str
    version: str
    settings: str


@dataclass(frozen=True, kw_only=True)
class ProfileJsonlProvenance:
    __record_set__: ClassVar[str] = "profile.jsonl/provenance"

    document_sha256: str
    media_type: str
    conversion: int
    schema: str
    schema_revision: str
    extractor: ProfileJsonlProvenanceExtractor
    redone: bool | None = None


@dataclass(frozen=True, kw_only=True)
class ProfileJsonl:
    __record_set__: ClassVar[str] = "profile.jsonl"
    __source_digest__: ClassVar[str] = "ac8be0a2992e1acabe608e90f328ff064883d83d64b23eb63adacd19b712fcb3"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})

    id: str
    document: str
    supported: bool
    values: ProfileJsonlValues
    provenance: ProfileJsonlProvenance
