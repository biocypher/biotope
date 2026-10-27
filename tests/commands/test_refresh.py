import json
import shutil

from graph_project import MANIFEST, built, findings, invoke, ok, refresh

from biotope.graph.inventory import plan_sources


def test_mv_keeps_the_graph_building_and_a_content_change_alone_is_reported_by_check_data(project):
    people = project / "data/study/push/people.csv"
    people.write_text(people.read_text() + "p3,Lin\n")
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 3)
    rows = ok("check-data").output.splitlines()
    assert any("people.csv" in row and "CORRUPTED" in row for row in rows)
    assert any("report.html" in row and "VALID" in row for row in rows)

    ok("mv", "data/study/push/people.csv", "data/study/current/people.csv")

    assert built(project) == ({"data/study/current/people.csv", "data/study/docs/report.html"}, 3)
    manifest = json.loads((project / MANIFEST).read_text())
    assert "current/people.csv#people" in {record["@id"] for record in manifest["recordSet"]}


def test_mv_of_a_folder_inside_a_dataset_keeps_the_graph_building(project):
    ok("mv", "-r", "data/study/push", "data/study/current")

    assert built(project) == ({"data/study/current/people.csv", "data/study/docs/report.html"}, 2)
    manifest = json.loads((project / MANIFEST).read_text())
    assert "current/people.csv#people" in {record["@id"] for record in manifest["recordSet"]}


def test_the_refresh_after_a_dataset_is_renamed_generates_into_the_root_that_holds_it(project):
    ok("mv", "-r", "data/study", "data/current")
    (project / "data/current/push/projects.csv").write_text("project_id,title\nx1,Atlas\n")

    refresh("data/current")

    assert (project / "graph/sources/study/push_projects_csv_projects/schema.py").is_file()
    assert built(project) == ({"data/current/push/people.csv", "data/current/docs/report.html"}, 2)


def test_mv_changes_nothing_while_the_annotation_file_is_invalid_and_works_once_it_is_fixed(project):
    annotation = project / "data/study/.biotope.yaml"
    valid = annotation.read_text()
    annotation.write_text(valid + "tables: [\n")
    before = (project / MANIFEST).read_bytes()

    failed = invoke("mv", "data/study/push/people.csv", "data/study/current/people.csv")

    assert failed.exit_code != 0 and "data/study/.biotope.yaml" in failed.output
    assert (project / "data/study/push/people.csv").is_file()
    assert (project / MANIFEST).read_bytes() == before
    annotation.write_text(valid)
    ok("mv", "data/study/push/people.csv", "data/study/current/people.csv")
    assert built(project) == ({"data/study/current/people.csv", "data/study/docs/report.html"}, 2)


def test_a_move_outside_biotope_fails_the_check_naming_the_old_and_the_new_id(project):
    (project / "data/study/current").mkdir()
    shutil.move(project / "data/study/push/people.csv", project / "data/study/current/people.csv")
    refresh()

    result = invoke("graph", "check", "--json")

    assert result.exit_code != 0
    assert any(
        "'push/people.csv#people'" in finding["message"] and "'current/people.csv#people'" in finding["message"]
        for finding in findings(result)
    ), findings(result)


def acknowledge(root):
    for status in plan_sources(root / MANIFEST, root / "graph/sources").statuses:
        if status.state == "drift":
            schema = status.path / "schema.py"
            schema.write_text(schema.read_text().replace(status.acknowledged, status.revision))


def test_new_data_of_the_same_shape_rebuilds_after_the_refresh_alone(project):
    annotation = project / "data/study/.biotope.yaml"
    annotation.write_text(
        annotation.read_text() + "description: One synthetic study.\n"
        "tables:\n"
        "  push/people.csv#people:\n"
        "    description: One row per person.\n"
        "    key: person_id\n"
        "    columns:\n"
        "      name:\n"
        "        description: The person's full name.\n"
        "        equivalentProperty: https://schema.org/name\n"
    )
    acknowledge(project)
    written = annotation.read_bytes()
    study = project / "data/study"
    (study / "push/people.csv").write_text("person_id,name\np1,Ada\np2,Grace\np3,Lin\n")
    (study / "push/projects.csv").write_text("project_id,title\nx1,Atlas\n")
    (study / "docs/report.html").write_text("<html><body>Report, downloaded again</body></html>")
    (study / "archive").mkdir()
    (study / "archive/people.csv").write_text("person_id,name\np0,Old\n")

    refresh()

    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 3)
    assert annotation.read_bytes() == written
    description = json.loads((project / MANIFEST).read_text())
    assert description["description"] == "One synthetic study."
    people = next(record for record in description["recordSet"] if record["@id"] == "push/people.csv#people")
    assert (people["description"], people["key"]) == (
        "One row per person.",
        {"@id": "push/people.csv#people/person_id"},
    )
    name = next(field for field in people["field"] if field["name"] == "name")
    assert (name["description"], name["equivalentProperty"]) == ("The person's full name.", "https://schema.org/name")
