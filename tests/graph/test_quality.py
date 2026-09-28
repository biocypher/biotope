"""Measurements of typed outputs and execution without an export dependency."""

from dataclasses import replace

import pytest
from synthetic_pipelines import EDGES, MEASURED_PIPELINE, NODES, RecordingWriter, emit_measured, link, node

from biotope.graph import build
from biotope.graph.quality import GraphStores, analyze_quality
from biotope.graph.reports import CheckFailed
from biotope.graph.runtime import RunContext


def test_quality_counts_evidence_and_empty_denominators():
    context = RunContext(MEASURED_PIPELINE)
    emit_measured(context)
    context.validate_references()
    report = analyze_quality(context.stores()).to_json()
    m = report["measurements"]
    assert m["population"] == {"test:node": 4, "test:unused": 0, "test:link": 3}
    names = m["properties"]["test:node"]["name"]
    assert (names["null"], names["blank"], names["missing"], names["total"]) == (1, 1, 2, 4)
    assert names["examples"][1] == {"value": "x" * 160, "truncated": True}
    assert m["properties"]["test:node"]["count"]["missing"] == 0
    assert m["properties"]["test:node"]["enabled"]["missing"] == 0
    assert m["properties"]["test:node"]["tags"]["empty_list"] == 4
    assert m["properties"]["test:unused"]["note"]["missing_rate"] is None
    assert m["connectivity"]["components"] == 3
    assert m["connectivity"]["size_distribution"] == {"1": 2, "2": 1}
    assert m["connectivity"]["isolated_total"] == 2
    assert m["connectivity"]["largest_share"] == 0.5
    assert m["concentration"]["test:link"]["target"]["top"][0] == {"id": "n:1", "count": 3, "share": 1.0}
    assert m["self_loops"]["test:link"] == {"count": 1, "total": 3, "rate": 1 / 3}
    loop = next(f for f in report["findings"] if f["code"] == "quality.self_loop")
    assert loop["examples"][0]["id"] == "e:2"
    assert loop["examples"][0]["evidence"][0]["location"] == "2"
    assert {"quality.empty_required", "quality.missing_property", "quality.self_loop"} <= {
        f["code"] for f in report["findings"]
    }

    context.map(NODES, node(4, None, ["v" * 200] * 8))
    bounded = analyze_quality(GraphStores(context.schema, context.nodes, context.edges, {})).to_json()
    values = bounded["measurements"]["properties"]["test:node"]["tags"]["examples"]
    assert values[-1] == {"value": ["v" * 160] * 5, "truncated": True}

    empty = analyze_quality(GraphStores(context.schema, {}, {}, {})).to_json()["measurements"]
    assert empty["connectivity"]["largest_share"] is None
    assert empty["self_loops"]["test:link"]["rate"] is None


def test_quality_executes_once_without_export_and_records_failures(tmp_path, monkeypatch, unchecked_definitions):
    calls: list[str] = []

    def run(context):
        calls.append("run")
        emit_measured(context)

    class ForbiddenWriter:
        def __init__(self):
            raise AssertionError("Quality instantiated BioCypher")

    monkeypatch.setattr(build, "BioCypherWriter", ForbiddenWriter)
    monkeypatch.chdir(tmp_path)
    measured = replace(MEASURED_PIPELINE, run=run)
    report = build.assess_pipeline(measured)
    assert calls == ["run"]
    assert report["operation"] == "quality" and report["state"] == "complete"
    assert report["outputs"] == [] and report["report_path"] is None
    assert report["quality"]["measurements"]["population"]["test:node"] == 4
    assert list(tmp_path.iterdir()) == []

    calls.clear()
    result = build.run_pipeline(measured, tmp_path / "build", writer=RecordingWriter(calls))
    assert calls == ["environment", "run", "export"]
    assert result["quality"] == report["quality"]

    def bad(context):
        raise ValueError("mapping failed")

    with pytest.raises(build.RunFailed, match="mapping failed") as failure:
        build.assess_pipeline(replace(MEASURED_PIPELINE, run=bad))
    assert failure.value.report["quality"]["state"] == "not_run"

    def dangling(context):
        context.map(EDGES, link(99, 98, 97))

    with pytest.raises(build.RunFailed) as failure:
        build.assess_pipeline(replace(MEASURED_PIPELINE, run=dangling))
    assert failure.value.report["quality"]["state"] == "not_run"
    assert failure.value.report["quality"]["blocked_by"] == "integrity.failed"
    assert "measurements" not in failure.value.report["quality"]

    def invalid(*a, **kw):
        raise CheckFailed({"state": "failed", "findings": [{"severity": "error", "message": "stale"}]})

    monkeypatch.setattr(build, "check_pipeline", invalid)
    with pytest.raises(build.RunFailed, match="stale") as failure:
        build.assess_pipeline(MEASURED_PIPELINE)
    assert failure.value.report["definitions"]["state"] == "failed"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["build"]
