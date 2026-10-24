import json
from collections.abc import Iterator
from typing import Any

from biotope.graph import Evidence, RunContext, SourceRecord

from ...paths import PROJECT_ROOT
from . import SOURCE
from .schema import (
    ProfileJsonl,
    ProfileJsonlProvenance,
    ProfileJsonlProvenanceExtractor,
    ProfileJsonlValues,
    ProfileJsonlValuesEmails,
    ProfileJsonlValuesEmailsEvidence,
    ProfileJsonlValuesName,
    ProfileJsonlValuesNameEvidence,
    ProfileJsonlValuesOrcid,
    ProfileJsonlValuesOrcidEvidence,
)


PATH = PROJECT_ROOT / "extracted/profile.jsonl"


def _cite(record: dict[str, Any], name: str, value: dict[str, Any]) -> Evidence | None:
    evidence = value.get("evidence")
    if value.get("value") is None or evidence is None:
        return None
    where = evidence["locator"] or f"characters {evidence['start']}-{evidence['end']}"
    return Evidence(
        record["document"],
        record["provenance"]["document_sha256"],
        "profile.jsonl",
        f"{name} at {where}: {evidence['quote']!r}",
    )


def _record(line: dict[str, Any]) -> ProfileJsonl:
    values, provenance = line["values"], line["provenance"]
    return ProfileJsonl(
        id=line["id"],
        document=line["document"],
        supported=line["supported"],
        values=ProfileJsonlValues(
            name=ProfileJsonlValuesName(
                value=values["name"]["value"],
                evidence=ProfileJsonlValuesNameEvidence(**values["name"]["evidence"])
                if values["name"]["evidence"]
                else None,
            ),
            orcid=ProfileJsonlValuesOrcid(
                value=values["orcid"]["value"],
                evidence=ProfileJsonlValuesOrcidEvidence(**values["orcid"]["evidence"])
                if values["orcid"]["evidence"]
                else None,
            ),
            emails=[
                ProfileJsonlValuesEmails(
                    value=item["value"],
                    evidence=ProfileJsonlValuesEmailsEvidence(**item["evidence"]) if item["evidence"] else None,
                )
                for item in values["emails"]
            ],
        ),
        provenance=ProfileJsonlProvenance(
            document_sha256=provenance["document_sha256"],
            media_type=provenance["media_type"],
            conversion=provenance["conversion"],
            schema=provenance["schema"],
            schema_revision=provenance["schema_revision"],
            extractor=ProfileJsonlProvenanceExtractor(
                name=provenance["extractor"]["name"],
                version=provenance["extractor"]["version"],
                settings=json.dumps(provenance["extractor"]["settings"], sort_keys=True),
            ),
            redone=provenance.get("redone"),
        ),
    )


def _read(config: None) -> Iterator[SourceRecord[ProfileJsonl]]:
    with PATH.open(encoding="utf-8") as stream:
        for text in stream:
            line = json.loads(text)
            cited = [
                _cite(line, "name", line["values"]["name"]),
                _cite(line, "orcid", line["values"]["orcid"]),
                *(_cite(line, "emails", item) for item in line["values"]["emails"]),
            ]
            yield SourceRecord(_record(line), tuple(item for item in cited if item is not None))


def load(context: RunContext) -> Iterator[SourceRecord[ProfileJsonl]]:
    yield from context.load(SOURCE, _read, None)
