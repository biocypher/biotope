import json
import os
import shutil
from pathlib import Path
from unittest import mock

import h5py
import numpy as np
import openpyxl
import pytest
from graph_project import MANIFEST, PEOPLE, built, findings, invoke, ok, refresh, snapshot

from biotope.graph.inventory import plan_sources


def test_mv_keeps_the_graph_building_and_a_content_change_alone_is_reported_by_check_data(project):
    people = project / "data/study/push/people.csv"
    people.write_text(people.read_text() + "p3,Lin\n")
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 3)
    rows = ok("check-data").output.splitlines()
    assert any("people.csv" in row and "CORRUPTED" in row for row in rows)
    assert any("report.html" in row and "VALID" in row for row in rows)

    ok("mv", "data/study/push/people.csv", "data/study/current/people.csv")

    rows = ok("check-data").output.splitlines()
    assert any("people.csv" in row and "CORRUPTED" in row for row in rows)
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


def test_a_dataset_file_whose_path_also_names_a_file_at_the_project_root_moves_with_its_dataset(project):
    (project / "data/study/data").mkdir()
    (project / "data/study/data/people.csv").write_text("person_id,name\np9,Kim\n")
    (project / "data/people.csv").write_text("person_id,name\np8,Lee\n")
    refresh()

    ok("mv", "-r", "data", "archive/data")

    refresh("archive/data/study")
    assert built(project) == ({"archive/data/study/push/people.csv", "archive/data/study/docs/report.html"}, 2)
    tables = {
        record["@id"]
        for record in json.loads((project / ".biotope/datasets/archive/data/study.jsonld").read_text())["recordSet"]
    }
    assert "data/people.csv#people" in tables


def test_mv_after_a_new_key_in_the_annotation_file_leaves_the_key_for_graph_check_to_report(project):
    annotation = project / "data/study/.biotope.yaml"
    annotation.write_text(annotation.read_text() + "tables:\n  push/people.csv#people:\n    key: person_id\n")

    ok("mv", "data/study/push/people.csv", "data/study/push/staff.csv")

    refresh()
    result = invoke("graph", "check", "--json")
    assert result.exit_code != 0
    assert any(
        finding["code"] == "source.drift" and "push/staff.csv#staff" in finding["message"]
        for finding in findings(result)
    ), findings(result)


def workbook(path: Path) -> None:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "people"
    sheet.append(["person_id", "name"])
    sheet.append(["p1", "Ada"])
    book.save(path)


def anndata(path: Path) -> None:
    with h5py.File(path, "w") as stored:
        stored.attrs["encoding-type"] = "anndata"
        frame = stored.create_group("obs")
        frame.attrs.update({"encoding-type": "dataframe", "_index": "_index", "column-order": ["label"]})
        frame.create_dataset("_index", data=np.array([b"a", b"b"]))
        frame.create_dataset("label", data=np.array([1, 2]))


@pytest.mark.parametrize(
    ("write", "old", "new", "table"),
    [
        (workbook, "people.xlsx", "staff.xlsx", "push/staff.xlsx#people"),
        (anndata, "obs.h5ad", "sample.h5ad", "push/sample.h5ad#obs"),
    ],
)
def test_mv_of_a_file_keeps_the_name_of_a_table_inside_it_through_the_refresh(project, write, old, new, table):
    write(project / "data/study/push" / old)
    refresh()

    ok("mv", f"data/study/push/{old}", f"data/study/push/{new}")
    refresh()

    assert table in {record["@id"] for record in json.loads((project / MANIFEST).read_text())["recordSet"]}
    suffix = Path(old).suffix
    assert not [finding for finding in findings(ok("graph", "check", "--json")) if suffix in json.dumps(finding)]
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


def orphans() -> dict[str, str]:
    return {
        finding["subject"]: finding["message"]
        for finding in findings(invoke("graph", "check", "--json"))
        if finding["code"] == "inventory.orphan"
    }


def declare(root, package, old, new):
    schema = root / "graph/sources/study" / package / "schema.py"
    schema.write_text(schema.read_text().replace(f'"{old}', f'"{new}'))


def test_the_new_id_declared_where_generate_and_check_say_after_a_move_outside_biotope_builds(project):
    (project / "data/study/current").mkdir()
    shutil.move(project / "data/study/push/people.csv", project / "data/study/current/people.csv")
    ok("add", "--rebake", "data/study")
    generation = ok("source", "generate", MANIFEST, "--out", "graph/sources").output
    generated = "graph/sources/study/current_people_csv_people"

    [message] = orphans().values()

    assert f"Delete {generated}, then declare the new ID in this package" in message
    assert message in generation
    shutil.rmtree(project / generated)
    declare(project, PEOPLE, "push/people.csv", "current/people.csv")
    refresh()
    acknowledge(project)
    assert built(project) == ({"data/study/current/people.csv", "data/study/docs/report.html"}, 2)


@pytest.mark.parametrize("implemented", [False, True])
def test_a_file_moved_back_outside_biotope_names_no_package_that_reads_it_for_deletion(project, implemented):
    study, interim = project / "data/study", "graph/sources/study/current_people_csv_people"
    (study / "current").mkdir()
    shutil.move(study / "push/people.csv", study / "current/people.csv")
    refresh()
    if implemented:
        loader = project / interim / "loader.py"
        loader.write_text(loader.read_text().split("\n", 1)[1])
    shutil.move(study / "current/people.csv", study / "push/people.csv")
    refresh()

    [(subject, message)] = orphans().items()

    assert subject == "study/current_people_csv_people"
    assert f"Delete graph/sources/study/{PEOPLE}" not in message
    assert f"delete {interim}" in message.lower()
    shutil.rmtree(project / interim)
    refresh()
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)


def test_a_file_moved_twice_outside_biotope_names_only_placeholders_for_deletion(project):
    study = project / "data/study"
    for old, new in (("push", "current"), ("current", "latest")):
        (study / new).mkdir()
        shutil.move(study / old / "people.csv", study / new / "people.csv")
        refresh()
    interim, latest = (f"graph/sources/study/{name}_people_csv_people" for name in ("current", "latest"))

    messages = orphans()

    assert f"Delete {latest}, then declare the new ID in this package" in messages[f"study/{PEOPLE}"]
    assert f"Delete {interim}," in messages["study/current_people_csv_people"]
    assert latest not in messages["study/current_people_csv_people"]
    shutil.rmtree(project / latest)
    declare(project, PEOPLE, "push/people.csv", "latest/people.csv")
    refresh()
    [(subject, message)] = orphans().items()
    assert subject == "study/current_people_csv_people"
    assert f"Delete {interim}," in message and f"Delete graph/sources/study/{PEOPLE}" not in message
    shutil.rmtree(project / interim)
    refresh()
    acknowledge(project)
    assert built(project) == ({"data/study/latest/people.csv", "data/study/docs/report.html"}, 2)


def descriptions(root):
    return sorted(
        path.relative_to(root / ".biotope/datasets").as_posix() for path in root.glob(".biotope/datasets/**/*")
    )


@pytest.mark.parametrize(
    ("moved", "named", "generated"),
    [
        ("data/raw/staff.csv", ("'people.csv#people'", "'staff.csv#staff'"), "staff_csv_staff"),
        ("data/current/staff.csv", ("'people.csv#people'", "'staff.csv#staff'"), "staff_csv_staff"),
        (
            "data/current/people.csv",
            ("'people.csv#people'", "'data/raw/people.csv'", "'data/current/people.csv'"),
            None,
        ),
    ],
)
def test_a_single_file_moved_outside_biotope_fails_the_check_naming_the_old_and_the_new_id(
    single, moved, named, generated
):
    (single / moved).parent.mkdir(exist_ok=True)
    shutil.move(single / "data/raw/people.csv", single / moved)

    for _ in range(2):
        refresh(moved)
        result = invoke("graph", "check", "--json")
        assert result.exit_code != 0
        assert any(all(name in finding["message"] for name in named) for finding in findings(result)), findings(result)
    assert descriptions(single) == sorted(
        {"data", "data/study.jsonld", Path(moved).parent.as_posix(), f"{moved}.jsonld"}
    )
    shutil.move(single / moved, single / "data/raw/people.csv")
    ok("add", "--rebake", "data/raw/people.csv")
    ok("mv", "data/raw/people.csv", moved)
    if generated is not None:
        shutil.rmtree(single / "graph/sources/people_csv" / generated)
    refresh(moved)
    assert built(single) == ({moved, "data/study/docs/report.html"}, 2)


def test_a_single_file_renamed_and_then_given_its_name_back_in_another_folder_fails_the_check(single):
    for old, new in (
        ("data/raw/people.csv", "data/current/staff.csv"),
        ("data/current/staff.csv", "data/archive/people.csv"),
    ):
        (single / new).parent.mkdir(exist_ok=True)
        shutil.move(single / old, single / new)
        refresh(new)

    result = invoke("graph", "check", "--json")

    assert result.exit_code != 0
    named = ("'people.csv#people'", "'data/raw/people.csv'", "'data/archive/people.csv'")
    assert any(all(name in finding["message"] for name in named) for finding in findings(result)), findings(result)
    shutil.move(single / "data/archive/people.csv", single / "data/raw/people.csv")
    ok("add", "--rebake", "data/raw/people.csv")
    ok("mv", "data/raw/people.csv", "data/archive/people.csv")
    shutil.rmtree(single / "graph/sources/people_csv/staff_csv_staff")
    refresh("data/archive/people.csv")
    assert built(single) == ({"data/archive/people.csv", "data/study/docs/report.html"}, 2)


def test_a_file_moved_outside_biotope_twice_is_named_at_its_last_path_to_every_package_it_left(single):
    raw = single / "data/raw"
    shutil.move(raw / "people.csv", raw / "staff.csv")
    refresh("data/raw/staff.csv")
    shutil.move(raw / "staff.csv", raw / "members.csv")
    refresh("data/raw/members.csv")

    result = invoke("graph", "check", "--json")

    assert result.exit_code != 0
    for old in ("'people.csv#people'", "'staff.csv#staff'"):
        assert any(
            old in finding["message"] and "'members.csv#members'" in finding["message"]
            for finding in findings(result)
            if finding["code"] == "inventory.orphan"
        ), findings(result)
    shutil.move(raw / "members.csv", raw / "people.csv")
    ok("add", "--rebake", "data/raw/people.csv")
    ok("mv", "data/raw/people.csv", "data/raw/members.csv")
    for package in ("staff_csv_staff", "members_csv_members"):
        shutil.rmtree(single / "graph/sources/people_csv" / package)
    refresh("data/raw/members.csv")
    assert built(single) == ({"data/raw/members.csv", "data/study/docs/report.html"}, 2)


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


def test_an_identical_copy_whose_path_differs_only_in_case_fails_the_refresh_naming_both(project):
    push = project / "data/study/push"
    before = snapshot(project)
    both = not (push / "PEOPLE.csv").exists()
    (push / "PEOPLE.csv").write_bytes((push / "people.csv").read_bytes())

    result = invoke("add", "--rebake", "data/study")

    if both:
        assert result.exit_code != 0
        assert "the paths push/PEOPLE.csv and push/people.csv differ only in case" in " ".join(result.output.split())
        (push / "PEOPLE.csv").unlink()
        assert snapshot(project) == before
    refresh()
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)


def test_new_data_of_the_same_shape_rebuilds_after_the_refresh_alone(project):
    study = project / "data/study"
    (study / "docs/about.html").write_text("<html><body>About the study</body></html>")
    refresh()
    annotation = study / ".biotope.yaml"
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
    (study / "push/people.csv").write_text("person_id,name\np1,Ada\np2,Grace\np3,Lin\n")
    (study / "push/projects.csv").write_text("project_id,title\nx1,Atlas\n")
    (study / "docs/report.html").write_text("<html><body>Page not found</body></html>")
    (study / "docs/about.html").write_text("<html><body>Page not found</body></html>")
    (study / "archive").mkdir()
    (study / "archive/people.csv").write_text("person_id,name\np0,Old\n")
    (study / "backup").mkdir()
    shutil.copy(study / "push/people.csv", study / "backup/people.csv")
    shutil.copy(study / "push/people.csv", study / "people.csv")

    refresh()

    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 3)
    assert annotation.read_bytes() == written
    description = json.loads((project / MANIFEST).read_text())
    files = {entry["@id"] for entry in description["distribution"]}
    assert {"docs/about.html", "docs/report.html", "push/people.csv"} <= files
    assert description["description"] == "One synthetic study."
    people = next(record for record in description["recordSet"] if record["@id"] == "push/people.csv#people")
    assert (people["description"], people["key"]) == (
        "One row per person.",
        {"@id": "push/people.csv#people/person_id"},
    )
    name = next(field for field in people["field"] if field["name"] == "name")
    assert (name["description"], name["equivalentProperty"]) == ("The person's full name.", "https://schema.org/name")
