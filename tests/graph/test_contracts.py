"""Mapping signatures are the contract, enforced before any data is loaded."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent
FIXTURE = TESTS / "composition"


def check(tmp_path, *names):
    """Run the real strict checker over selected fixture modules."""
    config = tmp_path / "pyrightconfig.json"
    config.write_text(
        json.dumps(
            {
                "include": [os.path.relpath(FIXTURE / name, tmp_path) for name in names],
                "typeCheckingMode": "strict",
                # The lowest supported interpreter: the contract must hold there too.
                "pythonVersion": "3.10",
                "extraPaths": [str(ROOT), str(TESTS)],
                "reportMissingTypeStubs": "none",
            }
        )
    )
    result = subprocess.run(
        [sys.executable, "-m", "pyright", "--project", str(config), "--pythonpath", sys.executable, "--outputjson"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except ValueError:  # pragma: no cover - only when Pyright itself cannot run
        pytest.fail(result.stderr or result.stdout)
    assert payload["summary"]["filesAnalyzed"] >= len(names), result.stdout + result.stderr
    return [item for item in payload["generalDiagnostics"] if item["severity"] == "error"]


def test_composition_keeps_intermediate_and_graph_types(tmp_path):
    assert check(tmp_path, "__init__.py", "schema.py", "mappings.py", "pipeline.py", "precise.py") == []


def test_incompatible_composition_fails_static_checking(tmp_path):
    lines = (FIXTURE / "invalid.py").read_text().splitlines()
    expected = {
        number: match.group(1).strip()
        for number, line in enumerate(lines, start=1)
        if (match := re.search(r"#\s*expect:\s*(.+)$", line))
    }
    # Grouped cases, one line each: argument identity, arity, keywords, input
    # order, output precision, the apply/map split, topology construction,
    # duplicate contract declaration and the absent dispatch/emission routes.
    assert len(expected) == 20
    reported: dict[int, list[str]] = {}
    for item in check(tmp_path, "invalid.py"):
        reported.setdefault(item["range"]["start"]["line"] + 1, []).append(item["message"])
    assert sorted(reported) == sorted(expected), reported
    for number, needle in expected.items():
        assert any(needle in message for message in reported[number]), (number, needle, reported[number])


def test_multi_stage_execution_combines_evidence_and_deduplicates():
    from composition.pipeline import PIPELINE, build

    from biotope.graph.runtime import RunContext

    context = RunContext(PIPELINE)
    build(context)
    context.validate_references()
    assert len(context.nodes) == 5
    assert len(context.edges) == 3
    donor = context.nodes["fixture:donor:d1"]
    # Two measurements from different sources reached the same donor object.
    assert {item.record_set for item in donor.evidence} == {"assay", "donors", "legacy"}
    assert donor.mappings == {"fixture:build-objects"}
    sample = context.nodes["fixture:sample:s1"]
    assert {item.record_set for item in sample.evidence} == {"assay", "donors"}
    assert context.findings[0]["policy"] == "unmatched_measurement"
    assert context.findings[0]["count"] == 1
