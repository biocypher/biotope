import json
import re
import shutil

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from graph_project import MANIFEST, findings, invoke, ok


PEOPLE = "push/people.csv#people"
COMMENT = "# Ada: ask the lab who keeps the second sheet.\n"


def described(root, manifest=MANIFEST):
    return json.loads((root / manifest).read_text())


def table(description, identity):
    return next(record for record in description["recordSet"] if record["@id"] == identity)


def column(record, name):
    return next(field for field in record["field"] if field["name"] == name)


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    root = tmp_path / "project"
    (root / "data/study/push").mkdir(parents=True)
    (root / "data/study/push/people.csv").write_text("person_id,name\np1,Ada\np2,Grace\n")
    (root / "data/raw").mkdir()
    (root / "data/raw/samples.csv").write_text("sample_id,person_id\ns1,p1\n")
    monkeypatch.chdir(root)
    ok("init", ".", "--no-prompt")
    return root


def test_add_and_annotate_write_only_the_values_given_and_keep_comments(fresh):
    ok("add", "data/study", "data/raw/samples.csv")
    folder, single = fresh / "data/study/.biotope.yaml", fresh / "data/raw/samples.csv.biotope.yaml"
    assert not (fresh / "graph").exists()
    written = {}
    for annotation in (folder, single):
        assert not yaml.safe_load(annotation.read_text())
        written[annotation] = annotation.read_text() + COMMENT
        annotation.write_text(written[annotation])

    ok("add", "--rebake", "data/study", "--description", "People of one study.", "--license", "")
    ok("add", "--rebake", "data/raw/samples.csv", "--creator", "Ada Lovelace", "--keyword", "samples")
    ok("annotate", "set", "data/study", "--table", PEOPLE, "description=One row per person.", "key=person_id")
    ok(
        "annotate",
        "set",
        "data/study",
        "--table",
        PEOPLE,
        "--column",
        "person_id",
        "description=The person's ID.",
        "equivalentProperty=https://schema.org/identifier",
    )
    ok(
        "annotate",
        "set",
        "data/raw/samples.csv",
        "--table",
        "samples.csv#samples",
        "--column",
        "sample_id",
        "description=",
    )
    for unknown in (("--table", "push/missing.csv#missing"), ("--table", PEOPLE, "--column", "missing")):
        before = folder.read_bytes()
        refused = invoke("annotate", "set", "data/study", *unknown, "description=Nothing.")
        assert refused.exit_code != 0 and unknown[-1] in refused.output
        assert folder.read_bytes() == before

    assert yaml.safe_load(folder.read_text()) == {
        "description": "People of one study.",
        "license": None,
        "tables": {
            PEOPLE: {
                "description": "One row per person.",
                "key": "person_id",
                "columns": {
                    "person_id": {
                        "description": "The person's ID.",
                        "equivalentProperty": "https://schema.org/identifier",
                    }
                },
            }
        },
    }
    assert yaml.safe_load(single.read_text()) == {
        "creator": {"name": "Ada Lovelace"},
        "keywords": ["samples"],
        "tables": {"samples.csv#samples": {"columns": {"sample_id": {"description": None}}}},
    }
    for annotation in (folder, single):
        assert annotation.read_text().startswith(written[annotation])


def test_the_description_is_the_data_with_the_annotation_file_over_it(fresh):
    config = fresh / ".biotope/config.yaml"
    settings = yaml.safe_load(config.read_text())
    settings["project_metadata"] = {"creator": "Project Lead", "license": "https://example.org/licence"}
    config.write_text(yaml.safe_dump(settings))
    annotation = fresh / "data/study/.biotope.yaml"
    annotation.write_text(
        "# Written before the first add.\n"
        "description: People of one study.\n"
        "creator:\n"
        "license: ''\n"
        "tables:\n"
        f"  {PEOPLE}:\n"
        "    description: One row per person.\n"
        "    key: person_id\n"
        "    columns:\n"
        "      person_id:\n"
        "        description: The person's ID.\n"
        "        equivalentProperty: https://schema.org/identifier\n"
    )
    written = annotation.read_bytes()
    ok("add", "data/study")
    ok("add", "data/raw/samples.csv")

    def shows_every_annotation(description):
        assert description["description"] == "People of one study."
        assert description["name"] == "data/study"
        assert "creator" not in description and "license" not in description
        people = table(description, PEOPLE)
        assert people["description"] == "One row per person."
        assert people["key"] == {"@id": f"{PEOPLE}/person_id"}
        assert column(people, "person_id")["description"] == "The person's ID."
        assert column(people, "person_id")["equivalentProperty"] == "https://schema.org/identifier"
        assert column(people, "name")["description"] not in ("", "The person's ID.")

    shows_every_annotation(described(fresh))
    samples = described(fresh, ".biotope/datasets/data/raw/samples.csv.jsonld")
    assert (samples["creator"]["name"], samples["license"]) == ("Project Lead", "https://example.org/licence")

    (fresh / "data/study/push/people.csv").write_text("person_id,name\np1,Ada\np2,Grace\np3,Lin\n")
    (fresh / "data/study/push/projects.csv").write_text("project_id,title\nx1,Atlas\n")
    ok("add", "--rebake", "data/study")
    assert annotation.read_bytes() == written
    shows_every_annotation(described(fresh))
    assert table(described(fresh), "push/projects.csv#projects")

    retired = invoke("add", "data/study", "--bake-to", "review.jsonld")
    assert retired.exit_code != 0 and "No such option" in retired.output
    (fresh / "authored.jsonld").write_text(json.dumps({"name": "study", "recordSet": []}))
    retired = invoke("source", "register", "authored.jsonld", "--name", "study", "--replace")
    assert retired.exit_code != 0 and "No such option" in retired.output


def test_a_file_set_takes_its_name_from_the_annotation_file_until_the_name_is_removed(fresh):
    events = fresh / "data/study/events"
    events.mkdir()
    for part in (0, 1):
        pq.write_table(pa.table({"k": [part]}), events / f"part-{part}.parquet")
    ok("add", "data/study")
    annotation = fresh / "data/study/.biotope.yaml"
    baked = described(fresh)
    annotation.write_text(
        "file_sets:\n  events/*.parquet: events\ntables:\n  events#events:\n    description: Events.\n"
    )
    ok("map", "inspect", MANIFEST)
    named = described(fresh)
    assert "events" in {entry["@id"] for entry in named["distribution"]}
    assert table(named, "events#events")["description"] == "Events."
    assert column(table(named, "events#events"), "k")["source"]["fileSet"] == {"@id": "events"}

    annotation.write_text("")
    ok("map", "inspect", MANIFEST)
    assert described(fresh) == baked


def test_a_hand_edit_of_the_annotation_file_reaches_graph_check_and_build(project):
    annotation = project / "data/study/.biotope.yaml"
    annotation.write_text(
        annotation.read_text() + f"tables:\n  {PEOPLE}:\n    columns:\n      name:\n        description: Full name.\n"
    )
    ok("graph", "check")
    assert column(table(described(project), PEOPLE), "name")["description"] == "Full name."
    ok("graph", "build")

    annotation.write_text(annotation.read_text() + "    key: person_id\n")
    checked = invoke("graph", "check", "--json")
    assert checked.exit_code != 0
    assert [finding["code"] for finding in findings(checked) if finding["severity"] == "error"] == ["source.drift"]
    assert table(described(project), PEOPLE)["key"] == {"@id": f"{PEOPLE}/person_id"}
    assert invoke("graph", "build").exit_code != 0

    annotation.write_text(annotation.read_text().replace("    key: person_id\n", ""))
    ok("graph", "check")
    assert "key" not in table(described(project), PEOPLE)
    ok("graph", "build")


def test_mv_carries_the_annotations_of_the_moved_file(fresh):
    ok("add", "data/study", "data/raw/samples.csv")
    ok("annotate", "set", "data/study", "--table", PEOPLE, "--column", "name", "description=Full name.")
    ok("annotate", "set", "data/raw/samples.csv", "description=One row per sample.")
    ok("annotate", "set", "data/raw/samples.csv", "--table", "samples.csv#samples", "description=Samples.")
    folder = fresh / "data/study/.biotope.yaml"
    folder.write_text(folder.read_text().replace(f"  {PEOPLE}:\n", f"  {PEOPLE}:  # the PuSH export\n"))

    ok("mv", "data/study/push/people.csv", "data/study/current/people.csv")
    ok("mv", "data/raw/samples.csv", "data/raw/sheets.csv")

    moved = "current/people.csv#people"
    assert re.search(rf"^  {re.escape(moved)}: +# the PuSH export$", folder.read_text(), re.MULTILINE)
    assert column(table(described(fresh), moved), "name")["description"] == "Full name."
    assert not (fresh / "data/raw/samples.csv.biotope.yaml").exists()
    assert yaml.safe_load((fresh / "data/raw/sheets.csv.biotope.yaml").read_text()) == {
        "description": "One row per sample.",
        "tables": {"sheets.csv#sheets": {"description": "Samples."}},
    }
    sheets = described(fresh, ".biotope/datasets/data/raw/sheets.csv.jsonld")
    assert (sheets["description"], table(sheets, "sheets.csv#sheets")["description"]) == (
        "One row per sample.",
        "Samples.",
    )

    shutil.move(fresh / "data/study/current/people.csv", fresh / "data/study/push/people.csv")
    rebaked = ok("add", "--rebake", "data/study")
    assert f"table '{moved}'" in " ".join(rebaked.output.split())


def test_annotations_reach_a_dotted_folder_and_a_file_beside_a_folder_of_its_stem(fresh):
    (fresh / "data/study.v2/push").mkdir(parents=True)
    (fresh / "data/study.v2/push/people.csv").write_text("person_id,name\np1,Ada\n")
    (fresh / "data/study.v2/push/other.csv").write_text("x,y\n1,2\n")
    ok("add", "data/study", "--description", "Release 1.")
    ok("add", "data/study.v2", "--description", "Release 2.")
    ok("add", "data/raw/samples.csv", "--description", "Our samples.")
    (fresh / "data/raw/samples").mkdir()
    (fresh / "data/raw/samples/notes.txt").write_text("An unrelated folder.\n")

    ok("annotate", "set", "data/study.v2", "--table", PEOPLE, "description=One row per person.")
    ok("annotate", "set", "data/raw/samples.csv", "description=Edited.")
    ok("queue")

    first = described(fresh, ".biotope/datasets/data/study.jsonld")
    second = described(fresh, ".biotope/datasets/data/study.v2.jsonld")
    assert (first["description"], second["description"]) == ("Release 1.", "Release 2.")
    assert table(second, PEOPLE)["description"] == "One row per person."
    assert described(fresh, ".biotope/datasets/data/raw/samples.csv.jsonld")["description"] == "Edited."
    ok("mv", "data/study.v2/push/people.csv", "data/study.v2/push/staff.csv")
    ok("rm", "-f", "data/study.v2/push/other.csv")
    assert (
        table(described(fresh, ".biotope/datasets/data/study.v2.jsonld"), "push/staff.csv#staff")["description"]
        == "One row per person."
    )


def test_a_date_in_the_annotation_file_reaches_the_description_as_written(fresh):
    ok("add", "data/study")
    annotation = fresh / "data/study/.biotope.yaml"
    annotation.write_text(annotation.read_text() + "datePublished: 2024-05-01\n")
    ok("mark", "data/study", "mapped")
    assert (described(fresh)["datePublished"], described(fresh)["biotope:status"]) == ("2024-05-01", "mapped")
    ok("add", "--rebake", "data/study")
    assert described(fresh)["datePublished"] == "2024-05-01"


def test_a_rebake_keeps_the_lineage_and_the_status_people_gave(fresh):
    (fresh / "data/clean").mkdir()
    (fresh / "data/clean/people.csv").write_text("person_id\np1\n")
    ok("add", "data/study", "data/raw/samples.csv")
    ok("add", "data/clean", "--derived-from", "data/study")
    ok("mark", "data/clean", "mapped", "--derived-from", "data/raw/samples.csv")
    ok("add", "--rebake", "data/clean")
    clean = described(fresh, ".biotope/datasets/data/clean.jsonld")
    assert clean["prov:wasDerivedFrom"] == [{"@id": "data/study"}, {"@id": "data/raw/samples.csv"}]
    assert clean["biotope:status"] == "mapped"
