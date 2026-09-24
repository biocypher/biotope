"""Build-local provenance references, shared by every exported node and edge."""

from __future__ import annotations

import json
from pathlib import Path

from biotope.graph.contracts import Evidence, GraphRecord
from biotope.graph.runtime import RunContext


PROVENANCE_PROPERTY = "biotope_provenance_id"
PROVENANCE_CATALOG = "provenance.json"
PROVENANCE_REFERENCE = {"property": PROVENANCE_PROPERTY, "catalog": PROVENANCE_CATALOG, "indexing": "zero-based"}
ProvenanceKey = tuple[tuple[str, ...], tuple[Evidence, ...]]


def _key(record: GraphRecord) -> ProvenanceKey:
    return tuple(sorted(record.mappings)), tuple(sorted(record.evidence))


class ProvenanceCatalog:
    """Normalize source descriptors, evidence locations and contributing mappings.

    All references are zero-based array indexes scoped to this build. Sorting the
    complete vocabulary makes references independent of mapping execution order.
    """

    def __init__(self, context: RunContext) -> None:
        keys = sorted({_key(row) for store in (context.nodes, context.edges) for row in store.values()})
        evidence = sorted({item for _, contributors in keys for item in contributors})
        sources = sorted({(item.artifact, item.version, item.record_set) for item in evidence})
        source_ids = {source: index for index, source in enumerate(sources)}
        evidence_ids = {item: index for index, item in enumerate(evidence)}
        self.record_ids = {key: index for index, key in enumerate(keys)}
        self.sources = [
            {"artifact": artifact, "version": version, "record_set": record_set}
            for artifact, version, record_set in sources
        ]
        self.evidence = [
            {"source": source_ids[(item.artifact, item.version, item.record_set)], "location": item.location}
            for item in evidence
        ]
        self.records = [
            {"mappings": list(mappings), "evidence": [evidence_ids[item] for item in contributors]}
            for mappings, contributors in keys
        ]

    def reference(self, record: GraphRecord) -> int:
        """Return the index of a graph object's provenance record."""
        return self.record_ids[_key(record)]

    def write(self, path: Path) -> None:
        """Write valid JSON with one catalog entry per line for inspection."""
        with path.open("w", encoding="utf-8") as stream:
            stream.write('{"schema_version":1,"report_kind":"biotope.provenance",')
            stream.write(
                f'"property":{json.dumps(PROVENANCE_PROPERTY)},"indexing":{json.dumps(PROVENANCE_REFERENCE["indexing"])},\n'
            )
            for offset, (name, entries) in enumerate(
                (("sources", self.sources), ("evidence", self.evidence), ("records", self.records))
            ):
                if offset:
                    stream.write(",\n")
                stream.write(json.dumps(name) + ":[\n")
                for index, entry in enumerate(entries):
                    if index:
                        stream.write(",\n")
                    stream.write(json.dumps(entry, separators=(",", ":"), allow_nan=False))
                stream.write("\n]")
            stream.write("\n}\n")
