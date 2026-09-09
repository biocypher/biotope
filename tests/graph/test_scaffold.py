"""The mechanical graph template stays contained and protects authored work."""

import json
import subprocess
import sys

from click.testing import CliRunner

from biotope.cli import cli


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

    # Strictly check the delivered boilerplate itself. Importing does not execute it.
    script = """
from dataclasses import replace
from biotope.graph import Topology
from biotope.graph.check import check_pipeline
from graph.mappings._example import MAPPING
from graph.pipelines.build_graph import PIPELINE
from graph.pipelines._example import map_records
from graph.paths import GRAPH_ROOT, PROJECT_ROOT
from graph.sources._example import SOURCE
from graph.topology._example_record.node import Record
from graph.topology._example_collection.node import Collection
from graph.topology._example_record.in_collection import InCollection
assert GRAPH_ROOT == PROJECT_ROOT / 'graph'
assert not PIPELINE.sources and not PIPELINE.mappings
assert not PIPELINE.topology.nodes and not PIPELINE.topology.edges
# Examples must be fresh, structurally valid and inert, even without source data.
report = check_pipeline(replace(
    PIPELINE,
    name='scaffold-contracts',
    scope='Illustrative declarations only; no research graph execution',
    sources=(SOURCE,),
    mappings=(MAPPING,),
    topology=Topology(nodes=(Record, Collection), edges=(InCollection,)),
))
assert any('example:' in warning for warning in report['warnings'])
assert any('No intent' in warning for warning in report['warnings'])
try:
    PIPELINE.run(None)
except NotImplementedError:
    pass
else:
    raise AssertionError('Unfinished template must not silently succeed')
"""
    checked = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, text=True, capture_output=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    unfinished = subprocess.run(
        [sys.executable, "-m", "biotope.cli", "graph", "check", "graph.pipelines.build_graph:PIPELINE"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert unfinished.returncode != 0
    assert "stable name and explicit selected scope" in unfinished.stderr
    assert {p.name for p in tmp_path.iterdir()} == {"raw", "purpose.txt", "graph"}

    pipeline = graph / "pipelines/build_graph.py"
    pipeline.write_text(pipeline.read_text() + "\n# Authored work must survive.\n")
    before = {p.relative_to(graph): p.read_bytes() for p in graph.rglob("*") if p.is_file()}
    again = runner.invoke(cli, ["graph", "scaffold"])
    assert again.exit_code != 0 and "already exists" in again.output
    assert before == {p.relative_to(graph): p.read_bytes() for p in graph.rglob("*") if p.is_file()}

    # A symlink is also existing work; do not follow it or populate its target.
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
    manifest = tmp_path / "reviewed.jsonld"
    manifest.write_text(
        json.dumps(
            {
                "recordSet": [
                    {"@id": "first", "name": "First", "field": [{"name": "id", "dataType": "sc:Text"}]},
                    {"@id": "reserved", "name": "RECORDS", "field": []},
                    # Match Open Targets' 337 top-level contracts without a real-data fixture.
                    *({"@id": f"table{i}", "name": f"Table{i}", "field": []} for i in range(335)),
                ]
            }
        )
    )
    output = tmp_path / "graph/sources/study/schema.py"
    args = ["source", "generate", str(manifest), "--out", str(output)]
    generated = runner.invoke(cli, args)
    assert generated.exit_code == 0, generated.output
    registration, loader = output.with_name("__init__.py"), output.with_name("loader.py")
    assert registration.is_file() and loader.is_file()
    registration.write_text(registration.read_text() + "\n# Authored registration\n")
    loader.write_text(loader.read_text() + "\n# Authored decoding policy\n")
    authored = (registration.read_bytes(), loader.read_bytes())
    data = json.loads(manifest.read_text())
    data["recordSet"].append({"@id": "later", "name": "Later", "field": []})
    manifest.write_text(json.dumps(data))
    regenerated = runner.invoke(cli, args)
    assert regenerated.exit_code == 0, regenerated.output
    assert (registration.read_bytes(), loader.read_bytes()) == authored
    assert runner.invoke(cli, [*args, "--check"]).exit_code == 0
    # Moving the whole project must preserve the metadata link; imports and checks never load it as data.
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
from graph.pipelines.build_graph import PIPELINE
from graph.sources.study import SOURCE
from graph.sources.study.schema import RECORDS
from graph.sources.study.loader import Config, load
assert SOURCE.metadata.is_file()
assert SOURCE.records == RECORDS
expected = ('first', 'reserved', *(f'table{i}' for i in range(335)), 'later')
assert tuple(row.__record_set__ for row in RECORDS) == expected
check_pipeline(replace(PIPELINE, name='source-setup', scope='declarations', sources=(SOURCE,)))
""",
        ],
        cwd=relocated,
        text=True,
        capture_output=True,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    absent = relocated / "graph/sources/absent/schema.py"
    assert runner.invoke(cli, ["source", "generate", "reviewed.jsonld", "--out", str(absent), "--check"]).exit_code != 0
    assert not absent.parent.exists()


def test_definition_check_reports_missing_purpose_and_requirements(tmp_path, monkeypatch):
    from pathlib import Path

    from biotope.graph import Pipeline, Topology
    from biotope.graph.check import check_pipeline
    from biotope.project_model import Project

    monkeypatch.chdir(tmp_path)
    pipeline = Pipeline("review", Topology(()), (), (), lambda ctx: None, scope="definitions", code_paths=(__file__,))
    assert any("No intent" in item for item in check_pipeline(pipeline, static=False)["warnings"])
    intent = Path("project.yaml")
    Project(name="review").dump(intent)
    warnings = check_pipeline(pipeline, static=False)["warnings"]
    assert any("No research purpose" in item for item in warnings)
    assert any("No required entities or relations" in item for item in warnings)
    Project(name="review", purpose="Which records belong to each collection?").dump(intent)
    warnings = check_pipeline(pipeline, static=False)["warnings"]
    assert not any("No research purpose" in item or "No intent" in item for item in warnings)
    assert any("No required entities or relations" in item for item in warnings)
