import shutil
import subprocess
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
EXAMPLE = REPOSITORY / "tests/fixtures/typed_graph"
PURPOSE = "A reviewer checks transformed sample scores against the people the samples come from."
SETUP = (
    ("init", ".", "--no-prompt", "--purpose", PURPOSE),
    ("source", "register", "metadata/study.jsonld", "--name", "study"),
    ("source", "generate", ".biotope/datasets/study.jsonld", "--out", "graph/sources"),
)


def biotope(root, *args):
    return subprocess.run([sys.executable, "-m", "biotope.cli", *args], cwd=root, text=True, capture_output=True)


def prepare(tmp_path):
    root = tmp_path / "project"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("__pycache__", ".biotope", "build"))
    sources = {path: path.read_bytes() for path in (root / "graph/sources").rglob("*.py")}
    for command in SETUP:
        result = biotope(root, *command)
        assert result.returncode == 0, result.stdout + result.stderr
    assert {path: path.read_bytes() for path in (root / "graph/sources").rglob("*.py")} == sources
    return root


def run(root, action="check", output=None):
    command = ["graph", action]
    if output:
        command += ["--out", "graph/build/" + output]
    return biotope(root, *command)
