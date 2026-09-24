"""Exported references recover all contributors, without repeated source descriptors."""

import csv
import json
from dataclasses import asdict

from test_context import PIPELINE

from biotope.graph import Evidence
from biotope.graph.output import BioCypherWriter
from biotope.graph.provenance import PROVENANCE_PROPERTY, ProvenanceCatalog
from biotope.graph.runtime import RunContext


def test_every_node_and_edge_reference_recovers_its_mapping_evidence(tmp_path):
    context = RunContext(PIPELINE)
    PIPELINE.run(context)
    # An identical graph result carries contributors from both occurrences.
    row = next(iter(context.nodes.values()))
    row.evidence.add(Evidence("paper.pdf", "v2", "paper/facts", "page 7"))
    BioCypherWriter().write(context, tmp_path)
    catalog = json.loads((tmp_path / "provenance.json").read_text())
    index = ProvenanceCatalog(context)
    for store in (context.nodes, context.edges):
        for record in store.values():
            entry = catalog["records"][index.reference(record)]
            restored = []
            for pointer in entry["evidence"]:
                evidence = catalog["evidence"][pointer]
                restored.append({**catalog["sources"][evidence["source"]], "location": evidence["location"]})
            assert restored == [asdict(item) for item in sorted(record.evidence)]
            assert entry["mappings"] == sorted(record.mappings)
    assert len(catalog["sources"]) == 2
    exported = 0
    for part in (tmp_path / "biocypher").glob("*-part000.csv"):
        header = next(csv.reader([part.with_name(part.name.replace("part000", "header")).read_text()]))
        with part.open() as stream:
            for values in csv.DictReader(stream, fieldnames=header):
                pointer = int(values[PROVENANCE_PROPERTY + ":long"])
                identity = values.get(":ID") or values["id"]
                record = (context.nodes if ":ID" in values else context.edges)[identity]
                assert pointer == index.reference(record)
                exported += 1
    assert exported == len(context.nodes) + len(context.edges)
    script = (tmp_path / "biocypher/neo4j-admin-import-call.sh").read_text()
    assert str(tmp_path) not in script
    assert "${BIOCYPHER_IMPORT_DIR}" in script


def test_identical_provenance_is_shared_and_order_independent(tmp_path):
    context = RunContext(PIPELINE)
    PIPELINE.run(context)
    first = ProvenanceCatalog(context)
    assert len(first.records) == 1
    context.nodes = dict(reversed(list(context.nodes.items())))
    context.edges = dict(reversed(list(context.edges.items())))
    second = ProvenanceCatalog(context)
    first.write(tmp_path / "first.json")
    second.write(tmp_path / "second.json")
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()
