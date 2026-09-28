import importlib.metadata

from synthetic_pipelines import RESULTS_PIPELINE, RecordingWriter

from biotope.graph import build


def test_imported_reader_libraries_must_be_declared_and_are_recorded(project, tmp_path, monkeypatch):
    (project.graph / "alignment/__init__.py").write_text("import json\nimport yaml\nfrom yaml import safe_load\n")
    report = project.report()
    assert report["imports"]["yaml"] == ["pyyaml"] and "json" not in report["imports"]
    [finding] = [f for f in report["findings"] if f["code"] == "dependencies.undeclared"]
    assert finding["subject"] == "pyyaml" and "graph/pyproject.toml" in finding["message"]

    pyproject = project.graph / "pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace('<0.11"]', '<0.11", "PyYAML>=6"]'))
    assert "dependencies.undeclared" not in project.codes()

    monkeypatch.setattr(build, "check_pipeline", lambda *args, **kwargs: {"imports": report["imports"]})
    recorded = build.run_pipeline(RESULTS_PIPELINE, tmp_path / "build", writer=RecordingWriter())["dependencies"]
    assert recorded["pyyaml"]["version"] == importlib.metadata.version("pyyaml")
