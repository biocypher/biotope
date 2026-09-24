"""Replacing generated builds preserves the last success and protects other files."""

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from synthetic_pipelines import RESULTS_PIPELINE, RecordingWriter, emit_results

from biotope.graph import build
from biotope.graph.artifacts import FAILURE_REPORT, RUN_REPORT


pytestmark = pytest.mark.usefixtures("unchecked_definitions")


def rebuild(output: Path, pipeline=RESULTS_PIPELINE, writer=None) -> dict:
    return build.run_pipeline(pipeline, output, writer=writer or RecordingWriter())


def tree(root: Path) -> dict[str, object]:
    return {
        str(path.relative_to(root)): os.readlink(path) if path.is_symlink() else path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_symlink() or path.is_file()
    }


def fail(context):
    raise ValueError("deliberate loader failure")


@pytest.mark.parametrize("schema_version", [1, 2])
def test_a_failed_rebuild_preserves_the_previous_build_and_a_successful_one_replaces_it(tmp_path, schema_version):
    output = tmp_path / "build"
    first = rebuild(output)
    previous = json.loads((output / RUN_REPORT).read_text())
    (output / RUN_REPORT).write_text(json.dumps({**previous, "schema_version": schema_version}))
    before = tree(output)
    with pytest.raises(build.RunFailed):
        rebuild(output, replace(RESULTS_PIPELINE, run=fail))
    assert json.loads((output / FAILURE_REPORT).read_text())["state"] == "failed"
    assert tree(output) == {**before, FAILURE_REPORT: (output / FAILURE_REPORT).read_bytes()}
    rebuilt = rebuild(output)
    assert rebuilt["graph_digest"] == first["graph_digest"]
    assert rebuilt["report_path"] == str(output / RUN_REPORT)
    assert json.loads((output / RUN_REPORT).read_text())["schema_version"] == 2
    assert not (output / FAILURE_REPORT).exists()
    assert list(tmp_path.iterdir()) == [output]


def authored_directory(output: Path) -> None:
    output.mkdir()
    (output / "notes.txt").write_text("authored")


def authored_run_json(output: Path) -> None:
    output.mkdir()
    (output / RUN_REPORT).write_text(json.dumps({"authored": True, "outputs": []}))


def build_with_an_authored_file(output: Path) -> None:
    rebuild(output)
    (output / "notes.txt").write_text("authored")


def build_with_a_symlink(output: Path) -> None:
    rebuild(output)
    (output.parent / "outside.txt").write_text("authored")
    (output / "outside").symlink_to(output.parent / "outside.txt")


def symlink_to_a_build(output: Path) -> None:
    rebuild(output.parent / "elsewhere")
    output.symlink_to(output.parent / "elsewhere")


REFUSED = {
    authored_directory: "unrecognized build directory",
    authored_run_json: "Refusing to replace authored",
    build_with_an_authored_file: "undeclared file",
    build_with_a_symlink: "undeclared file",
    symlink_to_a_build: "symlink build destination",
}


@pytest.mark.parametrize("destination", REFUSED)
def test_a_build_never_replaces_a_destination_it_did_not_generate(tmp_path, destination):
    output = tmp_path / "build"
    destination(output)
    before = tree(tmp_path)
    with pytest.raises(ValueError, match=REFUSED[destination]):
        rebuild(output)
    assert tree(tmp_path) == before


def test_a_file_authored_during_the_build_is_not_replaced(tmp_path):
    output = tmp_path / "build"
    rebuild(output)

    def author_meanwhile(context):
        emit_results(context)
        (output / "notes.txt").write_text("authored")

    before = tree(output)
    with pytest.raises(ValueError, match="undeclared file"):
        rebuild(output, replace(RESULTS_PIPELINE, run=author_meanwhile))
    assert tree(output) == {**before, "notes.txt": b"authored"}
    assert list(tmp_path.iterdir()) == [output]


def test_a_failed_publish_restores_the_previous_build(tmp_path, monkeypatch):
    output = tmp_path / "build"
    rebuild(output)
    before = tree(output)
    move = Path.replace

    def interrupt_first_publish(source: Path, target: Path) -> Path:
        if Path(target) == output:
            monkeypatch.setattr(Path, "replace", move)
            raise OSError("publish interrupted")
        return move(source, target)

    monkeypatch.setattr(Path, "replace", interrupt_first_publish)
    with pytest.raises(OSError, match="publish interrupted"):
        rebuild(output)
    assert tree(output) == before
    assert list(tmp_path.iterdir()) == [output]


def test_failed_first_export_leaves_a_report_and_can_be_rebuilt(tmp_path):
    class FailingWriter(RecordingWriter):
        def write(self, context, directory):
            super().write(context, directory)
            raise ValueError("failed after partial export")

    output = tmp_path / "build"
    with pytest.raises(build.RunFailed):
        rebuild(output, writer=FailingWriter())
    assert sorted(p.name for p in output.iterdir()) == [RUN_REPORT]
    assert json.loads((output / RUN_REPORT).read_text())["state"] == "failed"
    assert rebuild(output)["state"] == "complete"
