"""The operations desk's airport notes: one record per airline role statement.

One kind of document: a Markdown file whose `##` sections are airports, each identified by
its IATA code in the heading, and each stating which airlines use it as a hub or a focus city.

The reader is pure code. It parses headings with a regular expression and matches the two
statement shapes the notes use, so no text leaves this machine and no model reads the file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from biotope.extraction import Document, ExtractionError, Extractor, Schema

_SECTION = re.compile(r"^##[ \t]+(\S+)[ \t]*$")
_CLAIM = re.compile(r"(Hub|Focus city) for (.+)\.$")
_SEPARATOR = re.compile(r",\s*|\s+and\s+")
_IATA = re.compile(r"[A-Z]{3}")
_ROLES: dict[str, str] = {"Hub": "hub", "Focus city": "focus_city"}


@dataclass(frozen=True, kw_only=True)
class AirportRoleClaim:
    """One airline the notes name as using one airport in one role.

    Records to extract: one per airline named in each "Hub for ..." or "Focus city for ..."
    statement under an airport's `##` heading. Leave out everything else a section says: the
    desk's prose about an airport's size, location or connectivity names no airline role, and
    a section that names no hub or focus city yields no record.
    """

    __record_key__: ClassVar[tuple[str, ...]] = ("airport_iata", "airline_name", "role")

    airport_iata: str = field(
        metadata={
            "description": (
                "IATA three-letter code of the airport section the statement sits under, exactly as "
                "the heading writes it, for example JFK. The key for 'which airlines have a hub at JFK'."
            )
        }
    )
    airline_name: str = field(
        metadata={
            "description": (
                "The airline as the note names it: a marketing name, never a code, for example "
                "'Delta Air Lines'. The key for 'where does United have hubs'. It is not resolved to an "
                "airline code here, so it must be joined to an airline by name."
            )
        }
    )
    role: Literal["hub", "focus_city"] = field(
        metadata={
            "description": (
                "The role the note states for this airline at this airport: 'hub' for a 'Hub for "
                "<airline>' statement and 'focus_city' for a 'Focus city for <airline>' statement. "
                "The filter for 'which airports are a focus city, and for which airline'."
            )
        }
    )


class AirportNotesReader(Extractor):
    """Read the notes' role statements with code; the file is never sent to a service or a model."""

    name = "airport-notes-reader"
    version = "1"

    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]:
        sections = _sections(document.path.read_text(encoding="utf-8"), document)
        records: list[dict[str, Any]] = []
        for iata, paragraphs in sections:
            records.extend(_claims(iata, paragraphs, document))
        return records


def _sections(text: str, document: Document) -> list[tuple[str, list[tuple[int, str]]]]:
    """Split the notes into their `##` sections, each with its paragraph text and line numbers."""
    sections: list[tuple[str, list[tuple[int, str]]]] = []
    current: str | None = None
    paragraphs: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        heading = _SECTION.match(line)
        if heading is not None:
            if current is not None:
                sections.append((current, paragraphs))
            code: str = heading.group(1)
            if _IATA.fullmatch(code) is None:
                raise ExtractionError(
                    f"{document.path}: line {number}: section heading {code!r} is not an IATA code"
                )
            current = code
            paragraphs = []
        elif current is not None and line.strip():
            paragraphs.append((number, line.strip()))
    if current is not None:
        sections.append((current, paragraphs))
    if not sections:
        raise ExtractionError(f"{document.path}: no '## <IATA>' airport sections found")
    return sections


def _claims(
    iata: str, paragraphs: list[tuple[int, str]], document: Document
) -> list[dict[str, Any]]:
    """Turn one airport's "Hub for ..." and "Focus city for ..." statements into one record per airline."""
    records: list[dict[str, Any]] = []
    for number, paragraph in paragraphs:
        match = _CLAIM.fullmatch(paragraph)
        if match is None:
            if paragraph.startswith(("Hub", "Focus")):
                raise ExtractionError(
                    f"{document.path}: line {number}: states a role in an unexpected shape: {paragraph!r}"
                )
            continue
        role = _ROLES[match.group(1)]
        locator = f"line {number}"
        for airline in (name.strip() for name in _SEPARATOR.split(match.group(2))):
            if not airline:
                raise ExtractionError(f"{document.path}: line {number}: names an empty airline")
            records.append(
                {
                    "airport_iata": {"value": iata, "quote": paragraph, "locator": locator},
                    "airline_name": {"value": airline, "quote": paragraph, "locator": locator},
                    "role": {"value": role, "quote": paragraph, "locator": locator},
                }
            )
    if not records:
        raise ExtractionError(
            f"{document.path}: section {iata} states no hub and no focus city for any airline"
        )
    return records
