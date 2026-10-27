import json
import os
import shutil
from pathlib import Path
from unittest import mock

import openpyxl
import pytest
from graph_project import MANIFEST, built, findings, invoke, ok, refresh, snapshot

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


def test_a_single_file_dataset_moved_into_a_subfolder_keeps_its_id_through_the_refresh(single):
    ok("mv", "data/raw/people.csv", "data/raw/2026/people.csv")
    refresh("data/raw/2026/people.csv")

    assert built(single) == ({"data/raw/2026/people.csv", "data/study/docs/report.html"}, 2)


def test_a_folder_moved_to_another_parent_carries_every_description_in_it(single):
    ok("mv", "-r", "data/raw", "data/archive/raw")
    refresh("data/archive/raw/people.csv")
    assert built(single) == ({"data/archive/raw/people.csv", "data/study/docs/report.html"}, 2)

    ok("mv", "-r", "data", "archive/data")
    refresh("archive/data/study", "archive/data/archive/raw/people.csv")

    assert built(single) == ({"archive/data/archive/raw/people.csv", "archive/data/study/docs/report.html"}, 2)
    descriptions = single / ".biotope/datasets"
    assert sorted(path.relative_to(descriptions).as_posix() for path in descriptions.rglob("*")) == [
        "archive",
        "archive/data",
        "archive/data/archive",
        "archive/data/archive/raw",
        "archive/data/archive/raw/people.csv.jsonld",
        "archive/data/study.jsonld",
    ]


def test_mv_of_a_workbook_keeps_its_sheet_name_through_the_refresh(project):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "people"
    sheet.append(["person_id", "name"])
    sheet.append(["p1", "Ada"])
    book.save(project / "data/study/push/people.xlsx")
    refresh()

    ok("mv", "data/study/push/people.xlsx", "data/study/push/staff.xlsx")
    refresh()

    tables = {record["@id"] for record in json.loads((project / MANIFEST).read_text())["recordSet"]}
    assert "push/staff.xlsx#people" in tables
    assert not [finding for finding in findings(ok("graph", "check", "--json")) if "xlsx" in json.dumps(finding)]
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)


@pytest.mark.parametrize(
    ("move", "dataset", "people"),
    [
        (
            ("data/study/push/people.csv", "data/study/current/people.csv"),
            "data/study",
            "data/study/current/people.csv",
        ),
        (("-r", "data/study", "data/current"), "data/current", "data/current/push/people.csv"),
    ],
)
def test_mv_changes_nothing_while_the_annotation_file_is_invalid_and_works_once_it_is_fixed(
    project, move, dataset, people
):
    annotation = project / "data/study/.biotope.yaml"
    valid = annotation.read_text()
    annotation.write_text(valid + "tables: [\n")
    before = snapshot(project)

    failed = invoke("mv", *move)

    assert failed.exit_code != 0 and "data/study/.biotope.yaml" in failed.output
    assert snapshot(project) == before
    annotation.write_text(valid)
    ok("mv", *move)
    refresh(dataset)
    assert built(project) == ({people, f"{dataset}/docs/report.html"}, 2)


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


def descriptions(root):
    return sorted(
        path.relative_to(root / ".biotope/datasets").as_posix() for path in root.glob(".biotope/datasets/**/*")
    )


@pytest.mark.parametrize("moved", ["data/raw/staff.csv", "data/current/staff.csv"])
def test_a_single_file_moved_outside_biotope_fails_the_check_naming_the_old_and_the_new_id(single, moved):
    (single / moved).parent.mkdir(exist_ok=True)
    shutil.move(single / "data/raw/people.csv", single / moved)
    refresh(moved)

    result = invoke("graph", "check", "--json")

    assert result.exit_code != 0
    assert any(
        "'people.csv#people'" in finding["message"] and "'staff.csv#staff'" in finding["message"]
        for finding in findings(result)
    ), findings(result)
    assert descriptions(single) == sorted(
        {"data", "data/study.jsonld", Path(moved).parent.as_posix(), f"{moved}.jsonld"}
    )
    shutil.move(single / moved, single / "data/raw/people.csv")
    ok("add", "--rebake", "data/raw/people.csv")
    ok("mv", "data/raw/people.csv", moved)
    shutil.rmtree(single / "graph/sources/people_csv/staff_csv_staff")
    refresh(moved)
    assert built(single) == ({moved, "data/study/docs/report.html"}, 2)


@pytest.mark.parametrize(("failure", "message"), [("annotation", "people.csv.biotope.yaml"), ("disk", "disk full")])
def test_a_takeover_that_fails_changes_nothing_and_works_once_retried(single, failure, message):
    annotation = single / "data/raw/people.csv.biotope.yaml"
    valid = annotation.read_text()
    annotation.write_text(valid + ("tables: [\n" if failure == "annotation" else ""))
    (single / "data/current").mkdir()
    shutil.move(single / "data/raw/people.csv", single / "data/current/staff.csv")
    before = snapshot(single)
    replace, failed_once = os.replace, []

    def failing(source, destination):
        if failure == "disk" and str(destination).endswith(".jsonld") and not failed_once:
            failed_once.append(destination)
            raise OSError("disk full")
        return replace(source, destination)

    with mock.patch("os.replace", side_effect=failing):
        failed = invoke("add", "--rebake", "data/current/staff.csv")

    assert failed.exit_code != 0 and message in failed.output + str(failed.exception)
    assert snapshot(single) == before
    annotation.write_text(valid)
    refresh("data/current/staff.csv")
    result = invoke("graph", "check", "--json")
    assert result.exit_code != 0
    assert any(
        "'people.csv#people'" in finding["message"] and "'staff.csv#staff'" in finding["message"]
        for finding in findings(result)
    ), findings(result)
    assert (single / "data/current/staff.csv.biotope.yaml").read_text() == valid


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
