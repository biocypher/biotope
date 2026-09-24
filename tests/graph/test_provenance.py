"""Exported references recover all contributors, without repeated source descriptors."""

import csv
import json
from dataclasses import asdict

from synthetic_pipelines import RESULTS, RESULTS_PIPELINE, emit_results, result_row

from biotope.graph.output import BioCypherWriter
from biotope.graph.provenance import PROVENANCE_CATALOG, PROVENANCE_PROPERTY, ProvenanceCatalog
from biotope.graph.runtime import RunContext


def contributed_twice() -> RunContext:
    context = RunContext(RESULTS_PIPELINE)
    emit_results(context, ("a", "b"))
    context.map(RESULTS, result_row("a", artifact="paper.pdf"))
    return context


def test_every_exported_reference_recovers_its_contributors(tmp_path):
    context = contributed_twice()
    BioCypherWriter().write(context, tmp_path)
    catalog = json.loads((tmp_path / PROVENANCE_CATALOG).read_text())
    exported = []
    for part in (tmp_path / "biocypher").glob("*-part000.csv"):
        header = next(csv.reader([part.with_name(part.name.replace("part000", "header")).read_text()]))
        with part.open() as stream:
            for values in csv.DictReader(stream, fieldnames=header):
                identity = values.get(":ID") or values["id"]
                record = (context.nodes if ":ID" in values else context.edges)[identity]
                entry = catalog["records"][int(values[PROVENANCE_PROPERTY + ":long"])]
                evidence = [catalog["evidence"][pointer] for pointer in entry["evidence"]]
                restored = [{**catalog["sources"][item["source"]], "location": item["location"]} for item in evidence]
                assert restored == [asdict(item) for item in sorted(record.evidence)]
                assert entry["mappings"] == sorted(record.mappings)
                exported.append(identity)
    assert sorted(exported) == sorted([*context.nodes, *context.edges])
    assert len(catalog["sources"]) == 2


def test_identical_provenance_is_shared_and_independent_of_mapping_order(tmp_path):
    context = contributed_twice()
    first = ProvenanceCatalog(context)
    assert len(first.records) == 3 < len(context.nodes) + len(context.edges)
    context.nodes = dict(reversed(context.nodes.items()))
    context.edges = dict(reversed(context.edges.items()))
    first.write(tmp_path / "first.json")
    ProvenanceCatalog(context).write(tmp_path / "second.json")
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()
