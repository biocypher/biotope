"""Topology-only documents, evidence overlays and safe offline artifacts."""

import json
import re

import pytest
from click.testing import CliRunner
from test_quality import PIPELINE, Link, Node, emit_fixture

from biotope.cli import cli
from biotope.graph.sources import digest


def test_metagraph_declarations_overlays_and_safe_embedding(monkeypatch):
    from biotope.graph.metagraph import describe_metagraph, render_metagraph
    from biotope.graph.quality import GraphView, analyze_quality
    from biotope.graph.runtime import RunContext

    context = RunContext(PIPELINE)
    emit_fixture(context)
    quality = analyze_quality(GraphView(context.schema, context.nodes, context.edges, PIPELINE.requirements)).to_json()
    source = {
        "schema_version": 1,
        "report_kind": "biotope.quality",
        "operation": "quality",
        "state": "complete",
        "scope": "four records",
        "definitions": {"topology_digest": digest(context.schema)},
        "quality": quality,
    }
    monkeypatch.setattr(
        Node, "__doc__", "A <script>document</script> with [brackets] and </script><script>bad()</script>"
    )
    before = digest(context.schema)
    monkeypatch.setattr(Node, "display_name", "Sample measurement", raising=False)
    monkeypatch.setattr(Link, "display_name", "Measured with", raising=False)
    plain = describe_metagraph(PIPELINE.topology)
    assert plain["nodes"][0]["label"] == "Sample measurement"
    assert plain["edges"][0]["label"] == "Measured with"
    assert plain["nodes"][1]["label"] == "Unused"
    assert plain["topology_digest"] == before  # Display labels do not change graph identity.

    assert plain["nodes"][0]["count"] is None
    enriched = describe_metagraph(PIPELINE.topology, source)
    assert enriched["nodes"][0]["count"] == 4
    assert enriched["edges"][0]["observations"]["self_loops"]["count"] == 1
    assert enriched["report"]["scope"] == "four records"
    assert enriched["nodes"][0]["properties"][0]["statistics"] is not None
    html = render_metagraph(enriched)
    embedded = re.search(r'<script id="meta-graph-data" type="application/json">(.*?)</script>', html, re.S)[1]
    assert json.loads(embedded) == enriched
    assert "</script><script>bad()" not in html
    assert not re.search(r"<script[^>]+src=", html)
    assert "d3" in html and "Search concepts" in html
    # Reports are local build outputs; attribution ships with the package, not in every artifact.
    assert "%%NOTICE%%" not in html and "Apache License" not in html
    with pytest.raises(ValueError, match="topology"):
        describe_metagraph(PIPELINE.topology, {**source, "definitions": {"topology_digest": "different"}})
    incomplete = describe_metagraph(PIPELINE.topology, {**source, "state": "failed", "quality": {"state": "not_run"}})
    assert incomplete["nodes"][0]["count"] is None
    assert incomplete["report"]["state"] == "failed"
    legacy = describe_metagraph(PIPELINE.topology, {k: v for k, v in source.items() if k != "quality"})
    assert legacy["nodes"][0]["count"] is None and legacy["report"]["quality_state"] == "unmeasured"


def test_metagraph_does_not_import_pipeline_and_preserves_authored_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(mix_stderr=False)
    assert runner.invoke(cli, ["graph", "scaffold", "--graph", "alternate graph"]).exit_code == 0
    root = tmp_path / "alternate graph"
    (root / "pipelines/build_graph.py").write_text("raise AssertionError('must not import pipeline')\n")
    result = runner.invoke(cli, ["graph", "metagraph", "--graph", str(root), "--json"])
    assert result.exit_code == 0, (result.stdout, result.stderr)
    assert json.loads(result.stdout)["nodes"] == []
    assert not (root / "reports").exists()
    for _ in range(2):
        result = runner.invoke(cli, ["graph", "metagraph", "--graph", str(root)])
        assert result.exit_code == 0, result.stderr
    # Pipeline import failures must still produce saved, unmeasured assessments.
    for operation in ("quality", "build"):
        args = ["graph", operation, "--graph", str(root), "--json"]
        if operation == "build":
            args += ["--out", str(root / "build/failed")]
        result = runner.invoke(cli, args)
        assert result.exit_code == 1
        failed = json.loads(result.stdout)
        assert failed["quality"]["state"] == "not_run"
        saved = root / ("reports/quality.json" if operation == "quality" else "build/failed/run.json")
        assert json.loads(saved.read_text())["state"] == "failed"
        assert not (root / "build/failed/biocypher").exists()
    path = root / "reports/metagraph.html"
    assert path.exists()
    path.write_text("authored")
    assert runner.invoke(cli, ["graph", "metagraph", "--graph", str(root)]).exit_code != 0
    assert path.read_text() == "authored"
    link = root / "reports/link.html"
    link.symlink_to(path)
    assert runner.invoke(cli, ["graph", "metagraph", "--graph", str(root), "--out", str(link)]).exit_code != 0
    assert runner.invoke(cli, ["graph", "metagraph", "--json", "--out", "both.html"]).exit_code == 2
