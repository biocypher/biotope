"""Workspace selection, independent diagnostics and terminal/report boundaries."""

import json

from click.testing import CliRunner

from biotope.cli import cli


def test_workspace_selection_and_independent_definition_failures(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(mix_stderr=False)
    for folder in ("graph", "alternate graph"):
        created = runner.invoke(cli, ["graph", "scaffold", "--graph", folder, "--json"])
        assert created.exit_code == 0, created.output
        project = tmp_path / folder
        pipeline = project / "pipelines/build_graph.py"
        pipeline.write_text(
            pipeline.read_text().replace('name=""', 'name="review"').replace('scope=""', 'scope="test"')
        )
        # A missing code path must not prevent reporting a broken requirement.
        pipeline.write_text(
            pipeline.read_text()
            .replace("requirements={}", 'requirements={"entity:missing": "test:missing"}')
            .replace('"pipelines",', '"pipelines", "missing.py",')
        )
        pipeline.write_text(
            pipeline.read_text()
            .replace(
                "from biotope.graph import Pipeline, RunContext",
                "from pathlib import Path\nfrom biotope.graph import Pipeline, RunContext, SourceContract, Mapping",
            )
            .replace(
                "sources=SOURCES",
                'sources=tuple(SourceContract(n, Path(n + ".jsonld"), Path(n + ".py"), ()) '
                'for n in ("missing-a", "missing-b"))',
            )
            .replace(
                "mappings=MAPPINGS",
                'mappings=(Mapping(name="bad-a", function=build), Mapping(name="bad-b", function=build))',
            )
        )
        result = runner.invoke(cli, ["graph", "check", "--graph", folder, "--json"])
        assert result.exit_code != 0
        report = json.loads(result.stdout)
        assert report["state"] == "failed"
        assert {"code.paths", "requirements.invalid"} <= {f["code"] for f in report["findings"]}
        assert any(s["name"] == "python" and s["state"] == "skipped" for s in report["checks"])
        assert {f["subject"] for f in report["findings"] if f["code"] == "source.contract"} == {
            "missing-a",
            "missing-b",
        }
        assert {f["subject"] for f in report["findings"] if f["code"] == "mapping.contract"} == {"bad-a", "bad-b"}
        assert "\x1b" not in result.stdout
        assert not (project / "reports").exists()

    missing = runner.invoke(cli, ["graph", "check", "--graph", "absent", "--json"])
    assert missing.exit_code != 0
    assert json.loads(missing.stdout)["findings"][0]["code"] == "workspace.load"


def test_alternate_workspace_quality_uses_its_parent_and_isolates_json(tmp_path):
    import subprocess
    import sys

    from test_example import prepare

    root = prepare(tmp_path)
    selected = root / "alternate graph"
    (root / "graph").rename(selected)
    (selected / "__init__.py").write_text(
        "print('project import diagnostic')\nimport os\nos.write(1, b'native import diagnostic\\n')\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "biotope.cli", "graph", "quality", "--graph", str(selected), "--json"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["graph_objects"] == {"nodes": 3, "edges": 2}
    assert report["quality"]["state"] == "complete"
    assert report["outputs"] == []
    assert "project import diagnostic" in result.stderr and "native import diagnostic" in result.stderr
    assert not (selected / "build").exists()
    assert (selected / "reports/quality.json").exists()


def test_human_report_wraps_paths_and_renders_every_finding():
    from io import StringIO

    from rich.console import Console

    from biotope.commands._graph_output import GraphOutput

    path = "graph/mappings/44161_2025_626_MOESM3_ESM_[snRNAseq]_cohort_characteristics.py"
    report = {
        "report_kind": "biotope.definitions",
        "state": "failed",
        "checks": [],
        "findings": [
            {
                "code": "python.argument",
                "severity": "error",
                "subject": "Mapping [donor]",
                "message": "Expected DonorId; received SampleId.",
                "location": {"path": path, "line": 84, "column": 17},
            },
            {
                "code": "source.opaque",
                "severity": "warning",
                "subject": "a[0]",
                "message": "Opaque field",
                "location": None,
            },
        ],
    }
    stream = StringIO()
    renderer = GraphOutput("check", "graph/", False, console=Console(file=stream, width=64, color_system=None))
    with renderer:
        renderer.finding(report["findings"][0])
        assert "Expected DonorId; received SampleId." in stream.getvalue()
    renderer.finish(report)
    assert stream.getvalue().count("Expected DonorId; received SampleId.") == 1
    lines = stream.getvalue().splitlines()
    assert all(len(line) <= 64 for line in lines)
    assert "Mapping [donor]" in stream.getvalue() and "a[0]" in stream.getvalue()
    assert path + ":84:17" in "".join(line.strip() for line in lines)
    assert "Expected DonorId; received SampleId." in stream.getvalue()
