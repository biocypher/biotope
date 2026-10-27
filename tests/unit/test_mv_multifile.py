import json

from click.testing import CliRunner

from biotope.cli import cli


def invoke(*args):
    return CliRunner().invoke(cli, list(args))


def test_a_file_a_file_set_covers_is_renamed_only_within_its_pattern_and_never_removed_alone(tmp_path, monkeypatch):
    data = tmp_path / "data/ot"
    data.mkdir(parents=True)
    (data / "part-00.parquet").write_bytes(b"x")
    manifest = tmp_path / ".biotope/datasets/data/ot.jsonld"
    manifest.parent.mkdir(parents=True)
    fileset = {"@type": "cr:FileSet", "@id": "fs", "includes": "*.parquet"}
    manifest.write_text(json.dumps({"@type": "sc:Dataset", "name": "data/ot", "distribution": [fileset]}))
    monkeypatch.chdir(tmp_path)

    moved = invoke("mv", "data/ot/part-00.parquet", "data/ot/part-renamed.parquet")
    assert moved.exit_code == 0, moved.output
    assert json.loads(manifest.read_text())["distribution"] == [fileset]

    renamed = invoke("mv", "data/ot/part-renamed.parquet", "data/ot/renamed.txt")
    assert renamed.exit_code != 0 and "FileSet" in renamed.output
    removed = invoke("rm", "-f", "data/ot/part-renamed.parquet")
    assert removed.exit_code != 0 and "FileSet" in removed.output
    assert [path.name for path in data.iterdir()] == ["part-renamed.parquet"]
