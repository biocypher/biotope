"""Source revisions: what a revision covers, the contract store, and how drift is explained and acknowledged."""

import json
import re

from synthetic import file_object, record_set, states

from biotope.graph.inventory import plan_sources
from biotope.graph.revisions import DRIFT_LINE_LIMIT, ContractStore
from biotope.graph.sources import digest


def test_drift_names_the_changed_field_and_is_acknowledged_by_updating_the_digest(project):
    manifest = project.implemented_study(record_set("x", "f", "g"), record_set("y", "h"))
    recorded = set(project.store)
    assert len(recorded) == 2
    project.edit(manifest, lambda data: data["recordSet"][0]["field"][0].update(dataType="sc:Integer"))
    [drift] = [finding for finding in project.findings() if finding["code"] == "source.drift"]
    assert (drift["subject"], drift["severity"]) == ("study/x", "error")
    assert 'field x/f: dataType "sc:Text" -> "sc:Integer"' in drift["message"]
    assert {"operation": "changed", "pointer": "/recordSet/0/field/0/dataType"}.items() <= drift["examples"][0].items()
    assert project.store == recorded
    project.acknowledge_drift(manifest)
    assert project.codes("error") == {}
    assert project.codes("warning")["source.revision_unrecorded"] == ["study/x"]
    project.generate(manifest)
    assert "source.revision_unrecorded" not in project.codes()


def test_drift_without_recorded_history_shows_the_current_contract(project):
    manifest = project.implemented_study(record_set("x", "f", "g"))
    for entry in (project.root / ".biotope/contracts").iterdir():
        entry.unlink()
    project.edit(manifest, lambda data: data["recordSet"][0]["field"][1].update(dataType="sc:Float"))
    found = project.codes()
    assert found["source.drift"] == ["study/x"] and found["source.revision_unavailable"] == ["study/x"]
    [message] = project.messages("source.revision_unavailable")
    assert "x/g: sc:Float" in message


def test_checksum_context_and_order_changes_are_explained(project):
    paper = file_object("paper", "p.pdf", fmt="application/pdf")
    manifest = project.implemented_study(record_set("rows", "a", "b"), files=[paper])

    def drift():
        return {
            finding["subject"]: finding["message"]
            for finding in project.findings()
            if finding["code"] == "source.drift"
        }

    project.edit(manifest, lambda data: data["distribution"][1].update(sha256="1" * 64))
    found = drift()
    assert list(found) == ["study/p_pdf"] and "changed /distribution/sha256" in found["study/p_pdf"]
    project.generate(manifest)
    project.acknowledge_drift(manifest)
    project.edit(manifest, lambda data: data["@context"].update(dct="http://purl.org/dc/terms/"))
    found = drift()
    assert sorted(found) == ["study/p_pdf", "study/rows"]
    assert all("only @context changed" in message and "added /@context/dct" in message for message in found.values())
    project.generate(manifest)
    project.acknowledge_drift(manifest)
    assert not drift()
    project.edit(manifest, lambda data: data["recordSet"][0]["field"].reverse())
    found = drift()
    assert list(found) == ["study/rows"] and "field order changed" in found["study/rows"]


def test_the_drift_summary_names_every_kind_of_field_change_and_the_diff_is_cut_at_its_limit(project):
    later = [f"e{index}" for index in range(8)]
    manifest = project.implemented_study(record_set("rows", "a", "b", "c", *later))

    def change(data):
        fields = data["recordSet"][0]["field"]
        fields[0]["source"]["extract"]["column"] = "A2"
        fields[1]["biotope:columnIndex"] = 3
        fields[1]["biotope:nullable"] = False
        for field in fields[3:]:
            field["dataType"] = "sc:Integer"
        fields.pop(2)
        fields.append({"@id": "rows/new", "name": "new", "dataType": "sc:Text"})

    project.edit(manifest, change)
    [drift] = [finding for finding in project.findings() if finding["code"] == "source.drift"]
    lines = drift["message"].splitlines()[1:]
    for line in (
        "field added: rows/new",
        "field removed: rows/c",
        'field rows/a: extract {"column": "a"} -> {"column": "A2"}',
        "field rows/b: columnIndex null -> 3",
        "field rows/b: nullable true -> false",
        'field rows/e7: dataType "sc:Text" -> "sc:Integer"',
    ):
        assert line in lines
    assert len(lines) == DRIFT_LINE_LIMIT + 1 and re.fullmatch(r"\(\+\d+ more differences; see --json\)", lines[-1])
    assert len(drift["examples"]) > DRIFT_LINE_LIMIT


def test_the_contract_store_holds_preimages_and_ignores_a_tampered_entry(project):
    project.implemented_study(record_set("rows", "x"))
    store = ContractStore(project.root)
    [path] = [path for path in store.directory.iterdir() if json.loads(path.read_text())["kind"] == "recordSet"]
    entry = json.loads(path.read_text())
    assert sorted(entry) == ["definition", "digest", "kind"] and digest(entry["definition"]) == entry["digest"]
    assert path.stem == entry["digest"] and store.get(path.stem) == entry["definition"]
    entry["definition"]["tampered"] = True
    path.write_text(json.dumps(entry))
    assert store.get(path.stem) is None


def test_a_build_never_writes_history_and_generation_never_rewrites_a_drifted_schema(project):
    manifest = project.study(record_set("rows", "x"))
    project.generate(manifest)
    schema = project.sources / "study/rows/schema.py"
    reviewed = schema.read_bytes()
    project.edit(manifest, lambda data: data["recordSet"][0]["field"][0].update(dataType="sc:Integer"))
    recorded = set(project.store)
    result = project.run("graph", "build")
    assert result.exit_code != 0 and "changed since revision" in result.output
    assert project.store == recorded
    assert states(project.generate(manifest)) == {"rows": "drift"}
    assert schema.read_bytes() == reviewed and len(project.store) == len(recorded) + 1


def test_a_revision_ignores_key_order_curation_notes_payloads_and_other_record_sets(project):
    manifest = project.implemented_study(record_set("kept", "x"))
    schema = project.sources / "study/kept/schema.py"
    reviewed, before = schema.read_bytes(), project.report()["sources"]["study/kept"]

    def unrelated(data):
        data["biotope:curation"] = {"reason": "Reviewed again"}
        data["distribution"][0].update(sha256="1" * 64, dateModified="2026-09-09")

    project.edit(manifest, unrelated)
    manifest.write_text(json.dumps(json.loads(manifest.read_text()), sort_keys=True))
    after = project.report()["sources"]["study/kept"]
    assert after["digest"] != before["digest"] and after["contract_digest"] == before["contract_digest"]
    project.edit(manifest, lambda data: data["recordSet"].insert(0, record_set("inserted", "y")))
    assert states(project.generate(manifest)) == {"inserted": "created", "kept": "current"}
    assert schema.read_bytes() == reviewed


def test_reordering_record_sets_without_an_id_is_drift_never_a_conflict(project):
    positional = [{"name": "alpha", "field": []}, {"name": "beta", "field": []}]
    manifest = project.manifest("study", positional)
    project.generate(manifest)
    project.edit(manifest, lambda data: data["recordSet"].reverse())
    # Their identity is their position, so refusing here would leave no regeneration that could succeed.
    reordered = plan_sources(manifest, project.sources)
    assert states(reordered) == {"alpha": "drift", "beta": "drift"} and not reordered.conflicts
