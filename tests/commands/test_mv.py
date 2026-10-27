import errno
import json
import os
import shutil
from pathlib import Path
from unittest import mock

import yaml
from click.testing import CliRunner
from graph_project import MANIFEST, built, invoke, ok, refresh, snapshot


def test_a_mv_that_fails_puts_every_file_and_folder_back(project):
    annotation = project / "data/study/.biotope.yaml"
    annotation.write_text(annotation.read_text() + "tables:\n  push/people.csv#people:\n    description: People.\n")
    (project / "data/current/study").mkdir(parents=True)
    (project / "data/current/study/old.txt").write_text("kept\n")
    before = snapshot(project)
    move = shutil.move

    def failing(source, destination):
        if str(source).endswith(".jsonld"):
            raise OSError("disk full")
        return move(source, destination)

    with mock.patch("shutil.move", side_effect=failing):
        failed = invoke("mv", "-r", "data/study", "data/elsewhere")

    assert failed.exit_code != 0 and "disk full" in failed.output
    assert snapshot(project) == before

    failed = invoke("mv", "data/study/push/people.csv", "data/study/docs/report.html/people.csv")

    assert failed.exit_code != 0 and "nothing was moved" in failed.output
    assert snapshot(project) == before

    refused = invoke("mv", "-r", "-f", "data/study", "data/current")

    assert refused.exit_code != 0 and "data/current/study" in refused.output
    assert snapshot(project) == before


def test_a_mv_over_another_file_that_fails_keeps_it_and_one_that_succeeds_replaces_it(single):
    annotation = single / "data/raw/people.csv.biotope.yaml"
    annotation.write_text(annotation.read_text() + "tables:\n  people.csv#people:\n    description: People.\n")
    (single / "data/raw/staff.csv").write_text("person_id,name\ns1,Lin\n")
    before = snapshot(single)
    rename, replace, failed_once = os.rename, os.replace, []

    def failing(source, destination):
        if str(destination).endswith("people_csv_people/schema.py") and not failed_once:
            failed_once.append(destination)
            raise OSError("disk full")
        return replace(source, destination)

    with mock.patch("os.replace", side_effect=failing):
        failed = invoke("mv", "-f", "data/raw/people.csv", "data/raw/staff.csv")

    assert failed.exit_code != 0 and "disk full" in failed.output
    assert snapshot(single) == before

    def across_devices(real):
        def moving(source, destination):
            if str(source).endswith("people.csv"):
                raise OSError(errno.EXDEV, "Invalid cross-device link", str(source), None, str(destination))
            return real(source, destination)

        return moving

    with (
        mock.patch("os.rename", side_effect=across_devices(rename)),
        mock.patch("os.replace", side_effect=across_devices(replace)),
    ):
        failed = invoke("mv", "-f", "data/raw/people.csv", "data/raw/staff.csv")

    assert failed.exit_code != 0 and "nothing was moved" in failed.output
    assert snapshot(single) == before

    failed = invoke("mv", "data/raw/people.csv", ".gitignore/people.csv")

    assert failed.exit_code != 0 and "nothing was moved" in failed.output
    assert snapshot(single) == before

    people = (single / "data/raw/people.csv").read_text()
    ok("mv", "-f", "data/raw/people.csv", "data/raw/staff.csv")

    assert (single / "data/raw/staff.csv").read_text() == people
    assert built(single) == ({"data/raw/staff.csv", "data/study/docs/report.html"}, 2)


def test_mv_never_replaces_an_annotation_file(single):
    (single / "data/raw/staff.csv.biotope.yaml").write_text("# Notes on a file that is still to come.\n")
    before = snapshot(single)

    refused = invoke("mv", "-f", "data/raw/people.csv", "data/raw/staff.csv")

    assert refused.exit_code != 0 and "data/raw/staff.csv.biotope.yaml" in refused.output
    assert snapshot(single) == before


def test_mv_never_replaces_a_described_file(project):
    (project / "data/study/push/staff.csv").write_text("person_id,name\ns1,Lin\n")
    refresh()
    before = snapshot(project)

    refused = invoke("mv", "-f", "data/study/push/staff.csv", "data/study/push/people.csv")

    assert refused.exit_code != 0 and "biotope rm" in refused.output
    assert snapshot(project) == before


def baked(tmp_path, monkeypatch):
    from biotope.cli import cli

    runner = CliRunner()
    assert runner.invoke(cli, ["init", "baked", "--dir", str(tmp_path), "--no-prompt"]).exit_code == 0
    root = tmp_path / "baked"
    monkeypatch.chdir(root)
    shutil.copytree(Path(__file__).resolve().parents[1] / "fixtures/things", root / "data/things")
    (root / "data/solo").mkdir()
    (root / "data/solo/only.csv").write_text("id\n1\n")
    added = runner.invoke(cli, ["add", "data/things", "data/solo"])
    assert added.exit_code == 0, added.output
    return root, lambda *args: runner.invoke(cli, list(args))


def described(root, dataset):
    manifest = json.loads((root / f".biotope/datasets/{dataset}.jsonld").read_text())
    return {entry["contentUrl"] for entry in manifest["distribution"]}, manifest


def test_mv_accepts_files_baker_described_in_a_folder_manifest(tmp_path, monkeypatch):
    from biotope.utils import is_file_tracked

    root, run = baked(tmp_path, monkeypatch)
    assert described(root, "data/things")[0] == {"first.csv", "second.csv"}
    moved = run("mv", "data/things/first.csv", "data/things/renamed.csv")
    assert moved.exit_code == 0, moved.output
    assert described(root, "data/things")[0] == {"renamed.csv", "second.csv"}
    assert is_file_tracked(root / "data/things/renamed.csv", root)
    alone = run("mv", "data/solo/only.csv", "data/solo/single.csv")
    assert alone.exit_code == 0, alone.output
    assert described(root, "data/solo")[0] == {"single.csv"}
    assert sorted(path.name for path in (root / ".biotope/datasets/data").iterdir()) == ["solo.jsonld", "things.jsonld"]


def test_mv_refuses_what_it_cannot_carry_and_changes_nothing(tmp_path, monkeypatch):
    root, run = baked(tmp_path, monkeypatch)
    (root / "data/untracked.csv").write_text("id\n1\n")
    (root / ".biotope/notes.csv").write_text("id\n1\n")
    added = run("add", ".biotope/notes.csv")
    assert added.exit_code == 0, added.output
    before = snapshot(root)

    for args, reason in (
        (("data/untracked.csv", "data/moved.csv"), "is not tracked"),
        (("data/things/first.csv", "../outside.csv"), "outside biotope project"),
        (("data/things/first.csv", "data/things/first.csv"), "Source and destination are the same"),
        (("data/things/first.csv", "data/things/second.csv"), "exists. Use --force"),
        ((".biotope/notes.csv", ".biotope/moved.csv"), "biotope internal"),
        (("data/things/first.csv", "data/solo/first.csv"), "Cross-dataset"),
    ):
        refused = run("mv", *args)
        assert refused.exit_code != 0 and reason in refused.output, (args, refused.output)

    assert snapshot(root) == before


def test_mv_moves_records_into_a_folder_dataset_whose_bake_leaves_them_out(project):
    fixtures = Path(__file__).resolve().parents[1] / "fixtures/extraction"
    shutil.copy(fixtures / "schemas.py", project / "graph/extraction/schemas.py")
    (project / "src").mkdir()
    shutil.copy(fixtures / "rules.py", project / "src/rules.py")
    config = project / ".biotope/config.yaml"
    settings = yaml.safe_load(config.read_text())
    settings["extraction"] = {"extractor": "src/rules.py:LineExtractor", "version": "1", "line": 1}
    config.write_text(yaml.safe_dump(settings, sort_keys=False))
    schema = "graph/extraction/schemas.py:Profile"
    ok("extract", "run", schema, "data/study")

    ok("mv", "data/extracted/profile.jsonl", "data/study/records/profile.jsonl")

    refresh()
    extracted = ok("extract", "run", schema, "data/study", "--out", "data/study/records/profile.jsonl", "--json")
    assert {document["status"] for document in json.loads(extracted.stdout)["documents"]} == {"reused"}
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)
    manifest = json.loads((project / MANIFEST).read_text())
    identities = [entry["@id"] for entry in [*manifest["distribution"], *manifest["recordSet"]]]
    assert [identity for identity in identities if "profile" in identity] == []


def test_a_refused_move_into_another_dataset_advises_steps_that_keep_the_data(project):
    (project / "data/other").mkdir()
    (project / "data/other/projects.csv").write_text("project_id,title\nx1,Atlas\n")
    ok("add", "data/other")
    before = snapshot(project)

    refused = invoke("mv", "-r", "data/other", "data/study/other")

    advice = (
        "To make it part of data/study/, run biotope rm --keep-data data/other, which keeps the data, "
        "move it to data/study/other outside biotope, then run biotope add --rebake data/study."
    )
    assert refused.exit_code != 0 and advice in " ".join(refused.output.split())
    assert snapshot(project) == before
    ok("rm", "--keep-data", "-f", "data/other")
    shutil.move(project / "data/other", project / "data/study/other")
    refresh()
    assert (project / "data/study/other/projects.csv").read_text() == "project_id,title\nx1,Atlas\n"
    manifest = json.loads((project / MANIFEST).read_text())
    assert "other/projects.csv#projects" in {record["@id"] for record in manifest["recordSet"]}
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)
