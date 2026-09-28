"""The mechanical graph template stays contained and protects authored work."""

import json
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

from biotope.cli import cli
from biotope.graph import Pipeline, Topology
from biotope.graph.check import check_pipeline
from biotope.graph.render import render_inventory
from biotope.project_model import Project


def test_scaffold_is_independent_import_safe_and_refuses_existing_work(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw/untouched.csv").write_text("id\noriginal\n")
    (tmp_path / "purpose.txt").write_text("Existing scientific purpose\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["graph", "scaffold", "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    graph = tmp_path / "graph"
    assert report["path"] == str(graph)
    assert set(report["files"]) == {str(p.relative_to(graph)) for p in graph.rglob("*") if p.is_file()}
    assert {p.name for p in tmp_path.iterdir()} == {"raw", "purpose.txt", "graph"}
    assert (tmp_path / "raw/untouched.csv").read_text() == "id\noriginal\n"
    assert (tmp_path / "purpose.txt").read_text() == "Existing scientific purpose\n"
    assert not (graph / "build").exists()
    assert not (graph / "metadata").exists()

    script = """
from graph.pipelines.build_graph import PIPELINE
from graph.paths import GRAPH_ROOT, PROJECT_ROOT
from graph.sources import EXCLUDED_SOURCES, SOURCES
from graph.sources.inventory import INVENTORY
from graph.standardization import TERMS
assert GRAPH_ROOT == PROJECT_ROOT / 'graph'
assert INVENTORY == () and SOURCES == () and EXCLUDED_SOURCES == {} and TERMS == ()
assert PIPELINE.source_inventory is INVENTORY and PIPELINE.excluded_sources is EXCLUDED_SOURCES
assert PIPELINE.sources is SOURCES and PIPELINE.terms is TERMS
assert not PIPELINE.mappings and not PIPELINE.topology.nodes and not PIPELINE.topology.edges
try:
    PIPELINE.run(None)
except NotImplementedError:
    pass
else:
    raise AssertionError('Unfinished template must not silently succeed')
"""
    checked = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, text=True, capture_output=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert (graph / "sources/inventory.py").read_text() == render_inventory()
    assert not any(part.startswith("_example") for p in graph.rglob("*") for part in p.parts)
    unfinished = subprocess.run(
        [sys.executable, "-m", "biotope.cli", "graph", "check", "--json"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert unfinished.returncode != 0
    findings = json.loads(unfinished.stdout)["findings"]
    assert {(f["code"], f["severity"]) for f in findings} == {
        ("pipeline.invalid", "error"),
        ("intent.absent", "warning"),
    }
    assert "stable name and explicit selected scope" in unfinished.stdout
    assert {p.name for p in tmp_path.iterdir()} == {"raw", "purpose.txt", "graph"}

    pipeline = graph / "pipelines/build_graph.py"
    pipeline.write_text(pipeline.read_text() + "\n# Authored work must survive.\n")
    before = {p.relative_to(graph): p.read_bytes() for p in graph.rglob("*") if p.is_file()}
    again = runner.invoke(cli, ["graph", "scaffold"])
    assert again.exit_code != 0 and "already exists" in again.output
    assert before == {p.relative_to(graph): p.read_bytes() for p in graph.rglob("*") if p.is_file()}

    another = tmp_path / "another"
    another.mkdir()
    (another / "graph").symlink_to(graph, target_is_directory=True)
    monkeypatch.chdir(another)
    linked = runner.invoke(cli, ["graph", "scaffold"])
    assert linked.exit_code != 0
    assert before == {p.relative_to(graph): p.read_bytes() for p in graph.rglob("*") if p.is_file()}


def test_source_setup_is_explicit_portable_and_preserves_authored_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["graph", "scaffold"]).exit_code == 0
    (tmp_path / ".biotope").mkdir()
    manifest = tmp_path / "reviewed.jsonld"
    manifest.write_text(
        json.dumps(
            {
                "recordSet": [
                    {"@id": "first", "name": "First", "field": [{"@id": "first/id", "dataType": "sc:Text"}]},
                    {"@id": "schema", "name": "Schema", "field": []},
                    *({"@id": f"table{i}", "name": f"Table{i}", "field": []} for i in range(3)),
                ],
                "distribution": [
                    {
                        "@id": "doc",
                        "@type": "cr:FileObject",
                        "name": "paper.pdf",
                        "contentUrl": "paper.pdf",
                        "encodingFormat": "application/pdf",
                        "sha256": "0" * 64,
                    },
                    {"@id": "images", "@type": "cr:FileSet", "includes": "images/*.png", "encodingFormat": "image/png"},
                ],
            }
        )
    )
    sources = tmp_path / "graph/sources"
    args = ["source", "generate", str(manifest), "--out", str(sources), "--package", "study"]
    generated = runner.invoke(cli, args)
    assert generated.exit_code == 0, generated.output
    root = sources / "study"
    reserved = next(p for p in root.iterdir() if p.is_dir() and p.name.startswith("schema_"))
    registration, loader = root / "first/__init__.py", root / "first/loader.py"
    assert registration.is_file() and loader.is_file() and (reserved / "schema.py").is_file()
    assert (root / "__init__.py").read_text().startswith("# Generated by biotope;")
    assert (root / "paper_pdf/schema.py").is_file() and (root / "images/schema.py").is_file()
    assert len(list((tmp_path / ".biotope/contracts").iterdir())) == 7
    registration.write_text(registration.read_text() + "\n# Authored registration\n")
    loader.write_text(loader.read_text() + "\n# Authored decoding policy\n")
    authored = (registration.read_bytes(), loader.read_bytes())
    unrelated = (root / "table2/schema.py").read_bytes()
    data = json.loads(manifest.read_text())
    data["recordSet"].append({"@id": "later", "name": "Later", "field": []})
    manifest.write_text(json.dumps(data))
    regenerated = runner.invoke(cli, args)
    assert regenerated.exit_code == 0, regenerated.output
    assert (registration.read_bytes(), loader.read_bytes()) == authored
    assert "Created   graph/sources/study/later" in regenerated.output
    assert regenerated.output.count("Created ") == 1
    assert (root / "table2/schema.py").read_bytes() == unrelated
    assert runner.invoke(cli, [*args, "--check"]).exit_code == 0
    relocated = tmp_path.with_name(tmp_path.name + "-relocated")
    tmp_path.rename(relocated)
    monkeypatch.chdir(relocated)
    checked = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from dataclasses import replace
from biotope.graph.check import check_pipeline
from biotope.graph.reports import CheckFailed
from graph.pipelines.build_graph import PIPELINE
from graph.sources.study import CONTRACTS
from graph.sources.study.first import SOURCE
from graph.sources.study.first.schema import First
from graph.sources.study.first.loader import load
assert SOURCE.metadata.is_file()
assert SOURCE.name == 'study/first'
assert SOURCE.records == (First,)
expected = {'first', 'schema', *(f'table{i}' for i in range(3)), 'later', 'doc/facts', 'images/facts'}
assert {c.records[0].__record_set__ for c in CONTRACTS} == expected and len(CONTRACTS) == len(expected)
try:
    check_pipeline(replace(PIPELINE, name='source-setup', scope='declarations'))
except CheckFailed as exc:
    errors = [f for f in exc.report['findings'] if f['severity'] == 'error']
    assert {f['code'] for f in errors} == {'inventory.placeholder'}, errors
    assert len(errors) == len(expected)
else:
    raise AssertionError('Selected placeholder loaders must block the check')
""",
        ],
        cwd=relocated,
        text=True,
        capture_output=True,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    absent = relocated / "graph/sources/absent"
    check_absent = ["source", "generate", "reviewed.jsonld", "--out", str(absent.parent), "--package", "absent"]
    assert runner.invoke(cli, [*check_absent, "--check"]).exit_code != 0
    assert not absent.exists()


def test_definition_check_reports_missing_purpose_and_requirements(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pipeline = Pipeline("review", Topology(()), (), (), lambda ctx: None, scope="definitions", code_paths=(__file__,))
    assert any(f["code"] == "intent.absent" for f in check_pipeline(pipeline, static=False)["findings"])
    intent = Path("project.yaml")
    Project(name="review").dump(intent)
    warnings = [f["message"] for f in check_pipeline(pipeline, static=False)["findings"] if f["severity"] == "warning"]
    assert any("No research purpose" in item for item in warnings)
    assert any("No required entities or relations" in item for item in warnings)
    Project(name="review", purpose="Which records belong to each collection?").dump(intent)
    warnings = [f["message"] for f in check_pipeline(pipeline, static=False)["findings"] if f["severity"] == "warning"]
    assert not any("No research purpose" in item or "No intent" in item for item in warnings)
    assert any("No required entities or relations" in item for item in warnings)
