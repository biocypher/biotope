"""Core tests for biotope mv — multi-file cases live in test_mv_multifile.py."""

from __future__ import annotations

import errno
import json
import os
import shutil
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from graph_project import built, invoke, refresh, snapshot

from biotope.commands.mv import _resolve_destination_path, _validate_move_operation, mv


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def biotope_project_with_file(tmp_path):
    biotope_dir = tmp_path / ".biotope"
    datasets_dir = biotope_dir / "datasets"
    datasets_dir.mkdir(parents=True)

    data_dir = tmp_path / "data" / "inputs"
    data_dir.mkdir(parents=True)
    test_file = data_dir / "test.csv"
    test_file.write_text("gene,expression\nBRCA1,12.5")

    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "test",
        "description": "Dataset for test.csv",
        "distribution": [
            {
                "@type": "cr:FileObject",
                "@id": "file_12345678",
                "name": "test.csv",
                "contentUrl": "data/inputs/test.csv",
                "sha256": "abc123",
                "contentSize": 100,
                "dateCreated": "2023-01-01T00:00:00Z",
            }
        ],
    }
    metadata_dir = datasets_dir / "data" / "inputs"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "test.csv.jsonld").write_text(json.dumps(metadata, indent=2))
    return tmp_path


@pytest.mark.parametrize(
    "setup,message",
    [
        ("outside_dest", "outside biotope project"),
        ("same_path", "Source and destination are the same"),
        ("biotope_internal", "biotope internal"),
    ],
)
def test_validate_move_operation_rejects(biotope_project, setup, message):
    source = biotope_project / "data" / "file.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("x")

    if setup == "outside_dest":
        destination = biotope_project.parent / "outside.txt"
    elif setup == "same_path":
        destination = source
    else:
        source = biotope_project / ".biotope" / "config.yaml"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("config")
        destination = biotope_project / ".biotope" / "moved.yaml"

    with pytest.raises(click.Abort):
        _validate_move_operation(source, destination, biotope_project, force=False)


@pytest.mark.parametrize(
    "dest_input,expected_name",
    [
        ("/tmp/existing_dir", "file.txt"),
        ("/tmp/new/path/file.txt", "file.txt"),
        ("/tmp/existing.txt", "existing.txt"),
    ],
)
def test_resolve_destination_path(dest_input, expected_name, tmp_path):
    source = tmp_path / "file.txt"
    source.write_text("content")
    dest = Path(dest_input.replace("/tmp", str(tmp_path)))
    if dest.suffix:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("existing")
    else:
        dest.mkdir(parents=True, exist_ok=True)
    resolved = _resolve_destination_path(source, dest)
    assert resolved.name == expected_name


def test_mv_not_in_biotope_project(runner, tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(mv, ["a.txt", "b.txt"])
    assert result.exit_code != 0


def test_mv_file_not_tracked(runner, biotope_project):
    source = biotope_project / "test.csv"
    source.write_text("x")
    with runner.isolated_filesystem(temp_dir=biotope_project):
        result = runner.invoke(mv, [str(source), "moved.csv"])
    assert result.exit_code != 0
    assert "is not tracked" in result.output


def test_mv_successful_move(runner, biotope_project_with_file):
    source_file = biotope_project_with_file / "data" / "inputs" / "test.csv"
    destination = biotope_project_with_file / "data" / "outputs" / "test.csv"
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        result = runner.invoke(mv, [str(source_file), str(destination)])
        assert result.exit_code == 0
        assert "Move Complete" in result.output
        assert not source_file.exists()
        assert destination.exists()
        metadata_file = biotope_project_with_file / ".biotope" / "datasets" / "data" / "outputs" / "test.csv.jsonld"
        assert json.loads(metadata_file.read_text())["distribution"][0]["contentUrl"] == "data/outputs/test.csv"
    finally:
        os.chdir(original_cwd)


def test_mv_force_overwrite(runner, biotope_project_with_file):
    source_file = biotope_project_with_file / "data" / "inputs" / "test.csv"
    destination = biotope_project_with_file / "data" / "outputs" / "existing.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("existing content")
    original_cwd = Path.cwd()
    try:
        os.chdir(biotope_project_with_file)
        result = runner.invoke(mv, [str(source_file), str(destination), "--force"])
        assert result.exit_code == 0
        assert destination.read_text() == "gene,expression\nBRCA1,12.5"
    finally:
        os.chdir(original_cwd)


def test_a_failed_mv_puts_every_file_back(project):
    before = snapshot(project)
    move = shutil.move

    def failing(source, destination):
        if str(source).endswith(".jsonld"):
            raise OSError("disk full")
        return move(source, destination)

    with mock.patch("shutil.move", side_effect=failing):
        failed = invoke("mv", "-r", "data/study", "data/current")

    assert failed.exit_code != 0 and "disk full" in failed.output
    assert snapshot(project) == before
    refresh()
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)


def test_a_failed_mv_over_another_file_keeps_that_file(single):
    (single / "data/raw/staff.csv").write_text("person_id,name\ns1,Lin\n")
    before = snapshot(single)
    replace, failed_once = os.replace, []

    def failing(source, destination):
        if str(destination).endswith("people_csv_people/schema.py") and not failed_once:
            failed_once.append(destination)
            raise OSError("disk full")
        return replace(source, destination)

    with mock.patch("os.replace", side_effect=failing):
        failed = invoke("mv", "-f", "data/raw/people.csv", "data/raw/staff.csv")

    assert failed.exit_code != 0 and "disk full" in failed.output
    assert snapshot(single) == before
    refresh("data/raw/people.csv")
    assert built(single) == ({"data/raw/people.csv", "data/study/docs/report.html"}, 2)


@pytest.mark.parametrize(
    ("fixture", "moved", "dataset", "table", "under"),
    [
        (
            "project",
            "data/study/push/people.csv",
            "data/study",
            "push/people.csv#people",
            "data/study/docs/report.html",
        ),
        ("single", "data/raw/people.csv", "data/raw/people.csv", "people.csv#people", ".gitignore"),
    ],
)
def test_a_mv_that_fails_on_a_path_under_a_file_puts_every_file_and_folder_back(
    request, fixture, moved, dataset, table, under
):
    root = request.getfixturevalue(fixture)
    annotation = root / (f"{dataset}/.biotope.yaml" if fixture == "project" else f"{dataset}.biotope.yaml")
    annotation.write_text(annotation.read_text() + f"tables:\n  {table}:\n    description: People.\n")
    before = snapshot(root)

    failed = invoke("mv", moved, f"{under}/people.csv")

    assert failed.exit_code != 0 and "nothing was moved" in failed.output
    assert snapshot(root) == before
    refresh(dataset)
    assert built(root) == ({moved, "data/study/docs/report.html"}, 2)


def test_a_mv_that_cannot_rename_the_data_keeps_the_file_it_would_replace(single):
    (single / "data/raw/staff.csv").write_text("person_id,name\ns1,Lin\n")
    before = snapshot(single)
    rename, replace = os.rename, os.replace

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
    refresh("data/raw/people.csv")
    assert built(single) == ({"data/raw/people.csv", "data/study/docs/report.html"}, 2)


@pytest.mark.parametrize("force", [(), ("-f",)])
def test_mv_never_moves_a_folder_onto_an_existing_one(project, force):
    (project / "data/current/study").mkdir(parents=True)
    (project / "data/current/study/old.txt").write_text("kept\n")
    before = snapshot(project)

    refused = invoke("mv", "-r", *force, "data/study", "data/current")

    assert refused.exit_code != 0 and "data/current/study" in refused.output
    assert snapshot(project) == before
    refresh()
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)


@pytest.mark.parametrize("force", [(), ("-f",)])
def test_mv_never_replaces_an_annotation_file(single, force):
    (single / "data/raw/staff.csv.biotope.yaml").write_text("# Notes on a file that is still to come.\n")
    before = snapshot(single)

    refused = invoke("mv", *force, "data/raw/people.csv", "data/raw/staff.csv")

    assert refused.exit_code != 0 and "data/raw/staff.csv.biotope.yaml" in refused.output
    assert snapshot(single) == before
    refresh("data/raw/people.csv")
    assert built(single) == ({"data/raw/people.csv", "data/study/docs/report.html"}, 2)


def test_mv_never_replaces_a_described_file(project):
    (project / "data/study/push/staff.csv").write_text("person_id,name\ns1,Lin\n")
    refresh()
    before = snapshot(project)

    refused = invoke("mv", "-f", "data/study/push/staff.csv", "data/study/push/people.csv")

    assert refused.exit_code != 0 and "biotope rm" in refused.output
    assert snapshot(project) == before
    refresh()
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)


def test_mv_refuses_a_name_that_differs_from_another_file_only_in_case(project):
    (project / "data/study/push/staff.csv").write_text("person_id,name\ns1,Lin\n")
    refresh()
    before = snapshot(project)
    taken = (project / "data/study/push/PEOPLE.csv").exists()

    refused = invoke("mv", "data/study/push/staff.csv", "data/study/push/PEOPLE.csv")

    reason = "exists" if taken else "push/PEOPLE.csv and push/people.csv differ only in case"
    assert refused.exit_code != 0 and reason in refused.output
    assert snapshot(project) == before
    refresh()
    assert built(project) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)


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


def test_mv_refuses_to_move_a_file_out_of_its_folder_dataset(tmp_path, monkeypatch):
    root, run = baked(tmp_path, monkeypatch)
    before = snapshot(root)

    moved = run("mv", "data/things/first.csv", "data/solo/first.csv")

    assert moved.exit_code != 0 and "Cross-dataset" in moved.output
    assert snapshot(root) == before


@pytest.mark.parametrize("destination", ["data/study/docs/people.csv", "data/study/push/PEOPLE.csv"])
def test_mv_refuses_to_move_a_single_file_dataset_into_a_folder_dataset(single, destination):
    (single / "data/study/push").mkdir()
    (single / "data/study/push/people.csv").write_text("person_id,name\np5,Kai\n")
    refresh()
    before = snapshot(single)
    taken = (single / destination).exists()

    refused = invoke("mv", "data/raw/people.csv", destination)

    reason = "exists" if taken else "Cross-dataset move refused. data/raw/people.csv is described by"
    assert refused.exit_code != 0 and reason in refused.output
    assert snapshot(single) == before
    refresh("data/study", "data/raw/people.csv")
    assert built(single) == ({"data/raw/people.csv", "data/study/docs/report.html"}, 2)
