"""Replacing generated builds preserves the last success and protects other files."""

import json
from dataclasses import replace

import pytest
from test_quality import PIPELINE

from biotope.graph import build


class Writer:
    def check_environment(self):
        return {"exporter": "test", "version": "0", "format": "text"}

    def write(self, context, directory):
        (directory / "artifact.txt").write_text(str(len(context.nodes)))
        return ["artifact.txt"]


def test_successful_rebuild_replaces_outputs_and_failed_attempt_preserves_them(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})
    output = tmp_path / "build"
    first = build.run_pipeline(PIPELINE, output, writer=Writer())
    original = (output / "run.json").read_bytes()
    artifact = (output / "artifact.txt").read_bytes()

    def fail(context):
        raise ValueError("deliberate loader failure")

    with pytest.raises(build.RunFailed):
        build.run_pipeline(replace(PIPELINE, run=fail), output, writer=Writer())
    assert (output / "run.json").read_bytes() == original
    assert (output / "artifact.txt").read_bytes() == artifact
    assert json.loads((output / "last_failure.json").read_text())["state"] == "failed"
    rebuilt = build.run_pipeline(PIPELINE, output, writer=Writer())
    assert rebuilt["graph_digest"] == first["graph_digest"]
    assert rebuilt["report_path"] == str(output / "run.json")
    assert not (output / "last_failure.json").exists()
    assert list(tmp_path.iterdir()) == [output]


def test_rebuild_refuses_unrecognized_files_or_symlinks(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})
    output = tmp_path / "build"
    output.mkdir()
    notes = output / "notes.txt"
    notes.write_text("authored")
    with pytest.raises(ValueError, match="unrecognized"):
        build.run_pipeline(PIPELINE, output, writer=Writer())
    assert notes.read_text() == "authored"
    notes.unlink()
    output.rmdir()
    build.run_pipeline(PIPELINE, output, writer=Writer())
    notes.write_text("authored")
    with pytest.raises(ValueError, match="undeclared"):
        build.run_pipeline(PIPELINE, output, writer=Writer())
    notes.unlink()
    (output / "external").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="undeclared"):
        build.run_pipeline(PIPELINE, output, writer=Writer())


def test_failed_first_export_leaves_a_report_and_can_be_rebuilt(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})

    class FailingWriter(Writer):
        def write(self, context, directory):
            super().write(context, directory)
            raise ValueError("failed after partial export")

    output = tmp_path / "build"
    with pytest.raises(build.RunFailed):
        build.run_pipeline(PIPELINE, output, writer=FailingWriter())
    assert sorted(p.name for p in output.iterdir()) == ["run.json"]
    assert json.loads((output / "run.json").read_text())["state"] == "failed"
    assert build.run_pipeline(PIPELINE, output, writer=Writer())["state"] == "complete"
