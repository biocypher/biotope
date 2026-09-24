"""The shipped typed_graph example, copied into a fresh Biotope project."""

import shutil
import subprocess
import sys
from pathlib import Path

from biotope.graph.inventory import generate_source_packages
from biotope.graph.sources import register_metadata


EXAMPLE = Path(__file__).resolve().parents[2] / "examples/typed_graph"


def prepare(tmp_path):
    root = tmp_path / "project"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("__pycache__", ".biotope", "build"))
    (root / ".biotope").mkdir(exist_ok=True)
    manifest = register_metadata(root, root / "metadata/study.jsonld", "study", reason="Reviewed synthetic fixture-v1")
    plan = generate_source_packages(manifest, root / "graph/sources")
    assert {status.state for status in plan.statuses} == {"current"} and not plan.changes
    assert len(list((root / ".biotope/contracts").iterdir())) == 2
    return root


def run(root, action="check", output=None):
    command = [sys.executable, "-m", "biotope.cli", "graph", action]
    if output:
        command += ["--out", "graph/build/" + output]
    return subprocess.run(command, cwd=root, text=True, capture_output=True)
