import json
import shutil
from pathlib import Path

from click.testing import CliRunner

from biotope.cli import cli


THINGS = Path(__file__).resolve().parents[1] / "fixtures/things"


def baked(tmp_path, monkeypatch, *folders):
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "baked", "--dir", str(tmp_path), "--no-prompt"]).exit_code == 0
    root = tmp_path / "baked"
    monkeypatch.chdir(root)
    for folder in folders:
        shutil.copytree(THINGS, root / folder)
    added = runner.invoke(cli, ["add", *folders])
    assert added.exit_code == 0, added.output
    return root, lambda *args: runner.invoke(cli, list(args))


def files(folder):
    return {path.name: path.read_bytes() for path in folder.iterdir()}


def test_rm_removes_a_whole_dataset_by_its_folder_or_its_id_and_refuses_an_untracked_folder(tmp_path, monkeypatch):
    root, run = baked(tmp_path, monkeypatch, "data/things", "data/kept", "data/gone")
    (root / "data/untracked").mkdir()
    kept = files(root / "data/kept")

    refused = run("rm", "-f", "data/untracked")
    assert refused.exit_code != 0 and "not a tracked dataset" in refused.output
    removed = run("rm", "-f", "data/things")
    assert removed.exit_code == 0, removed.output
    assert not (root / "data/things").exists()
    assert not (root / ".biotope/datasets/data/things.jsonld").exists()
    removed = run("rm", "-f", "--keep-data", "data/kept")
    assert removed.exit_code == 0, removed.output
    assert files(root / "data/kept") == kept
    assert not (root / ".biotope/datasets/data/kept.jsonld").exists()
    shutil.rmtree(root / "data/gone")
    removed = run("rm", "-f", "data/gone")
    assert removed.exit_code == 0, removed.output
    assert not (root / ".biotope/datasets/data/gone.jsonld").exists()


def test_rm_accepts_a_file_baker_described_in_a_folder_manifest(tmp_path, monkeypatch):
    root, run = baked(tmp_path, monkeypatch, "data/things")
    things = root / "data/things"
    removed = run("rm", "-f", "data/things/second.csv")
    assert removed.exit_code == 0, removed.output
    assert not (things / "second.csv").exists()
    manifest = json.loads((root / ".biotope/datasets/data/things.jsonld").read_text())
    assert [entry["contentUrl"] for entry in manifest["distribution"]] == ["first.csv"]
    [kept] = manifest["recordSet"]
    assert {field["name"] for field in kept["field"]} == {"a", "b"}
    removed = run("rm", "-f", "--keep-data", "data/things/first.csv")
    assert removed.exit_code == 0, removed.output
    assert (things / "first.csv").is_file()
    assert not (root / ".biotope/datasets/data/things.jsonld").exists()
