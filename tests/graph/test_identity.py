"""Identity and precedence on an invented project: genes of two studies, people from four sources."""

import csv
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from biotope.cli import cli
from biotope.graph.inventory import generate_source_packages
from biotope.graph.sources import register_metadata


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/identity"
MANIFESTS = {
    "genes": "metadata/genes.jsonld",
    "people": "metadata/people.jsonld",
    "publications": "metadata/publications.jsonld",
    "extracted/profile": "metadata/profile.jsonld",
}
EGFR = "ensembl:ENSG00000146648"
ILSE, JONAS = "0000-0004-1234-5671", "0000-0004-7890-1239"
JON = "0000-0005-6789-0121"
PAPER = "doi:10.5555/reach.0001"


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    root = tmp_path / "project"
    shutil.copytree(FIXTURE, root, ignore=shutil.ignore_patterns("__pycache__", "build"))
    (root / ".biotope").mkdir()
    for name, path in MANIFESTS.items():
        manifest = register_metadata(root, root / path, name, reason="Invented identity fixture")
        plan = generate_source_packages(manifest, root / "graph/sources")
        assert {status.state for status in plan.statuses} == {"current"} and not plan.changes
    monkeypatch.chdir(root)
    return root


def build(root: Path, name: str = "first") -> tuple[dict, Path]:
    result = CliRunner(mix_stderr=False).invoke(cli, ["graph", "build", "--json", "--out", f"graph/build/{name}"])
    return json.loads(result.stdout), root / "graph/build" / name


def built(root: Path, name: str = "first") -> tuple[dict, dict]:
    report, output = build(root, name)
    assert report["state"] == "complete", report.get("error")
    return report["identity"], json.loads((output / "entities.json").read_text())


def holding(entities: dict, record: str) -> dict:
    [entity] = [item for item in entities["entities"] if record in [member["id"] for member in item["records"]]]
    return entity


def members(entity: dict) -> list[str]:
    return [member["id"] for member in entity["records"]]


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new))


def exported(output: Path, label: str) -> dict[str, dict]:
    part = output / "biocypher" / f"{label}-part000.csv"
    header = next(csv.reader([part.with_name(part.name.replace("part000", "header")).read_text()]))
    with part.open() as stream:
        rows = list(csv.DictReader(stream, fieldnames=header))
    return {row.get(":ID") or f"{row[':START_ID']}>{row[':END_ID']}": row for row in rows}


def evidence(output: Path, row: dict) -> list[dict]:
    catalog = json.loads((output / "provenance.json").read_text())
    record = catalog["records"][int(row["biotope_provenance_id:long"])]
    items = [catalog["evidence"][pointer] for pointer in record["evidence"]]
    return [{**catalog["sources"][item["source"]], "location": item["location"]} for item in items]


def test_genes_merge_on_ensembl_ids_and_take_the_symbol_of_the_first_study(root):
    identity, entities = built(root)
    genes = {item["id"]: item for item in entities["entities"] if item["concept"] == "fixture:gene"}
    assert len(genes) == 5
    egfr = genes[EGFR]
    assert members(egfr) == ["study_a:3", "study_b:1"]
    assert [member["sources"] for member in egfr["records"]] == [["genes/study_a"], ["genes/study_b"]]
    assert egfr["keys"] == {"ensembl": ["ENSG00000146648"]}
    assert egfr["fields"]["symbol"] == {"value": "EGFR", "sources": ["genes/study_a"], "records": ["study_a:3"]}
    [conflict] = [item for item in identity["conflicts"] if item.get("entity") == EGFR]
    assert conflict == {
        "concept": "fixture:gene",
        "entity": EGFR,
        "field": "symbol",
        "values": [
            {"source": "genes/study_a", "record": "study_a:3", "value": "EGFR"},
            {"source": "genes/study_b", "record": "study_b:1", "value": "ERBB1"},
        ],
        "chosen": "EGFR",
        "chosen_source": "genes/study_a",
    }
    unmapped = holding(entities, "study_a:4")
    assert unmapped["id"].startswith("fixture:gene-") and unmapped["derived"]
    assert unmapped["keys"] == {}

    edit(root / "graph/alignment/__init__.py", "(STUDY_A, STUDY_B)", "(STUDY_B, STUDY_A)")
    reversed_identity, reversed_entities = built(root, "reversed")
    assert holding(reversed_entities, "study_a:4")["id"] == unmapped["id"]
    egfr["fields"]["symbol"] = {"value": "ERBB1", "sources": ["genes/study_b"], "records": ["study_b:1"]}
    assert reversed_entities["entities"] == entities["entities"]
    conflict.update(chosen="ERBB1", chosen_source="genes/study_b")
    assert reversed_identity["conflicts"] == identity["conflicts"]
    assert reversed_entities["relations"] == entities["relations"]


def test_people_merge_transitively_and_every_build_gives_the_same_entities(root):
    report, output = build(root)
    identity = report["identity"]
    entities = json.loads((output / "entities.json").read_text())
    ilse = holding(entities, "roster:recIlse0001")
    assert members(ilse) == ["directory:i.brandt@example.org", "profile:data/pages/ilse.html", "roster:recIlse0001"]
    assert ilse["keys"] == {
        "emails": ["i.brandt@example.org", "ilse.brandt@example.org", "ilse@lab.example.org"],
        "orcid": [ILSE],
        "roster": ["recIlse0001"],
    }
    assert [member["sources"] for member in ilse["records"]] == [
        ["people/directory"],
        ["profile/profile_jsonl"],
        ["people/roster"],
    ]
    jonas = holding(entities, "roster:recJonas0002")
    assert members(jonas) == [
        "directory:jonas.keller@example.org",
        "profile:data/pages/jonas.html",
        "roster:recJonas0002",
    ]
    assert jonas["fields"]["name"] == {
        "value": "Jonas Keller",
        "sources": ["people/roster", "profile/profile_jsonl"],
        "records": ["profile:data/pages/jonas.html", "roster:recJonas0002"],
    }
    assert {"concept": "fixture:person", "entity": jonas["id"], "field": "name"}.items() <= next(
        item for item in identity["conflicts"] if item.get("entity") == jonas["id"]
    ).items()
    assert members(holding(entities, "roster:recGrete0003")) == ["roster:recGrete0003"]
    assert members(holding(entities, "roster:recJon0004")) == ["roster:recJon0004"]
    assert identity["entities"]["fixture:person"] == {"entities": 5, "records": 9, "merged": 2, "derived_ids": 5}
    relations = {(item["source"], item["target"]): item for item in entities["relations"]}
    assert set(relations) == {(ilse["id"], PAPER), (jonas["id"], PAPER)}
    edges = exported(output, "Authored")
    assert set(edges) == {f"{ilse['id']}>{PAPER}", f"{jonas['id']}>{PAPER}"}

    people = exported(output, "Person")
    cited = evidence(output, people[ilse["id"]])
    assert {
        "artifact": "raw/roster.csv",
        "version": "fixture-v1",
        "record_set": "roster",
        "location": "line:2",
    } in cited
    [orcid] = [item for item in cited if item["location"].startswith("orcid")]
    assert orcid["artifact"] == "data/pages/ilse.html" and orcid["record_set"] == "profile.jsonl"
    assert ILSE in orcid["location"] and "characters 87-106" in orcid["location"]

    compose = root / "graph/pipelines/compose.py"
    edit(
        compose,
        "STAGES = (study_a, study_b, roster, directory, profile, matches, push, openalex)",
        "STAGES = (openalex, push, matches, profile, directory, roster, study_b, study_a)",
    )
    for path in (root / "raw").glob("*.csv"):
        header, *rows = path.read_text().splitlines()
        random.Random(path.name).shuffle(rows)
        path.write_text("\n".join([header, *reversed(rows)]) + "\n")
    profile = root / "extracted/profile.jsonl"
    profile.write_text("\n".join(reversed(profile.read_text().splitlines())) + "\n")
    shuffled, shuffled_output = build(root, "shuffled")
    assert shuffled["identity"] == identity
    assert (shuffled_output / "entities.json").read_bytes() == (output / "entities.json").read_bytes()

    written = (output / "entities.json").read_bytes()
    shutil.rmtree(root / "graph/build")
    again, again_output = build(root, "first")
    assert again["identity"] == identity
    assert (again_output / "entities.json").read_bytes() == written


def test_a_record_that_bridges_two_people_stays_apart_and_both_stay_whole(root):
    _, before = built(root, "before")
    with (root / "raw/roster.csv").open("a") as stream:
        stream.write(f"recNew0005,Ilse Brandt,ilse.brandt@example.org,{JONAS}\n")
    identity, entities = built(root, "after")
    ilse, jonas = holding(entities, "roster:recIlse0001"), holding(entities, "roster:recJonas0002")
    assert ilse == holding(before, "roster:recIlse0001")
    assert jonas == holding(before, "roster:recJonas0002")
    apart = holding(entities, "roster:recNew0005")
    assert members(apart) == ["roster:recNew0005"] and apart["kept_apart"]
    [contradiction] = identity["contradictions"]
    assert contradiction == {
        "concept": "fixture:person",
        "keys": {"orcid": [ILSE, JONAS], "roster": ["recIlse0001", "recJonas0002", "recNew0005"]},
        "entities": sorted([ilse["id"], jonas["id"]]),
        "apart": [{"record": "roster:recNew0005", "entity": apart["id"]}],
    }
    relations = {(item["source"], item["target"]) for item in entities["relations"]}
    assert relations == {(ilse["id"], PAPER), (jonas["id"], PAPER)}


def test_a_matchers_links_merge_automatically_and_a_bridging_link_stays_apart(root):
    subprocess.run([sys.executable, "matchers/similar_names.py"], cwd=root, check=True)
    assert "semapv:LexicalMatching" in (root / "raw/matches.sssom.tsv").read_text()
    identity, entities = built(root)
    grete = holding(entities, "roster:recGrete0003")
    assert members(grete) == ["directory:grete.hansen@example.org", "roster:recGrete0003"]
    link = {
        "subject_id": "roster:recGrete0003",
        "object_id": "directory:grete.hansen@example.org",
        "mapping_justification": "semapv:LexicalMatching",
    }
    assert grete["automatic"] == [link]
    assert identity["automatic_merges"] == [{"concept": "fixture:person", "entity": grete["id"], **link}]
    jonas, jon = holding(entities, "roster:recJonas0002"), holding(entities, "roster:recJon0004")
    assert members(jon) == ["roster:recJon0004"] and not jon["kept_apart"]
    assert len(members(jonas)) == 3 and jonas["automatic"] == []
    [contradiction] = identity["contradictions"]
    assert contradiction == {
        "concept": "fixture:person",
        "keys": {"orcid": [JONAS, JON], "roster": ["recJon0004", "recJonas0002"]},
        "entities": sorted([jonas["id"], jon["id"]]),
        "apart": [
            {
                "link": {
                    "subject_id": "roster:recJon0004",
                    "object_id": "directory:jonas.keller@example.org",
                    "mapping_justification": "semapv:LexicalMatching",
                }
            }
        ],
    }


def test_a_bridging_record_and_a_bridging_link_in_one_group_leave_every_person_whole(root):
    _, before = built(root, "before")
    subprocess.run([sys.executable, "matchers/similar_names.py"], cwd=root, check=True)
    with (root / "raw/roster.csv").open("a") as stream:
        stream.write(f"recNew0005,Ilse Brandt,ilse.brandt@example.org,{JONAS}\n")
    identity, entities = built(root, "after")
    for record in ("roster:recIlse0001", "roster:recJonas0002", "roster:recJon0004"):
        assert members(holding(entities, record)) == members(holding(before, record))
    [contradiction] = identity["contradictions"]
    assert [part.get("record") or part["link"]["subject_id"] for part in contradiction["apart"]] == [
        "roster:recNew0005",
        "roster:recJon0004",
    ]


def test_combined_lists_one_relation_from_two_sources_and_undeclared_disagreement(root):
    report, output = build(root)
    entities = json.loads((output / "entities.json").read_text())
    ilse = holding(entities, "roster:recIlse0001")
    assert ilse["fields"]["emails"] == {
        "value": ["ilse.brandt@example.org", "i.brandt@example.org", "ilse@lab.example.org"],
        "sources": ["people/directory", "people/roster", "profile/profile_jsonl"],
        "records": ["directory:i.brandt@example.org", "profile:data/pages/ilse.html", "roster:recIlse0001"],
    }
    assert not [item for item in report["identity"]["conflicts"] if item.get("field") == "emails"]
    [relation] = [item for item in entities["relations"] if item["source"] == ilse["id"]]
    assert relation["sources"] == ["publications/openalex", "publications/push"]
    assert relation["fields"]["position"] == {"value": 1, "sources": ["publications/push"]}
    [conflict] = [item for item in report["identity"]["conflicts"] if item.get("field") == "position"]
    assert conflict == {
        "concept": "fixture:authored",
        "relation": {"source": ilse["id"], "target": PAPER},
        "field": "position",
        "values": [
            {"source": "publications/openalex", "value": 2},
            {"source": "publications/push", "value": 1},
        ],
        "chosen": 1,
        "chosen_source": "publications/push",
    }
    edge = exported(output, "Authored")[f"{ilse['id']}>{PAPER}"]
    assert edge["position:long"] == "1"
    assert {item["artifact"] for item in evidence(output, edge)} == {"raw/push.csv", "raw/openalex.csv"}

    edit(root / "graph/alignment/__init__.py", '{"title": (PUSH, OPENALEX)}', "{}")
    failed, _ = build(root, "undeclared")
    assert failed["state"] == "failed"
    for named in (PAPER, "title", "'Identity across sources'", "'Identity Across Sources'"):
        assert named in failed["error"]


def test_check_names_declarations_that_do_not_fit_the_topology_or_sources(root):
    result = CliRunner(mix_stderr=False).invoke(cli, ["graph", "check", "--json"])
    assert result.exit_code == 0, result.stdout
    report = json.loads(result.stdout)
    assert report["identity"]["fixture:person"] == {
        "keys": {"roster": "single", "orcid": "single", "emails": "multiple"},
        "natural": None,
    }
    assert report["precedence"]["fixture:authored"] == {
        "fields": {"position": ["publications/push", "publications/openalex"]},
        "combine": [],
    }
    alignment = root / "graph/alignment/__init__.py"
    edit(alignment, 'Key("emails")', 'Key("mail")')
    edit(alignment, '"title": (PUSH, OPENALEX)', '"headline": (PUSH, OPENALEX)')
    edit(alignment, 'Key("orcid", single=True)', 'Key("orcid", single=True), Key("emails", single=True)')
    result = CliRunner(mix_stderr=False).invoke(cli, ["graph", "check", "--json"])
    report = json.loads(result.stdout)
    assert result.exit_code != 0
    messages = [item["message"] for item in report["findings"] if item["code"] == "identity.invalid"]
    assert any("fixture:person" in message and "mail" in message for message in messages)
    assert any("fixture:paper" in message and "headline" in message for message in messages)
    assert any("emails" in message and "single" in message for message in messages)
