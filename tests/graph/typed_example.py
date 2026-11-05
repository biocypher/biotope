import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
EXAMPLE = REPOSITORY / "examples/typed_graph"
TUTORIAL = REPOSITORY / "docs/tutorial.md"
PREFIX = "uv run --project graph biotope "


def tutorial_commands():
    blocks = re.findall(r"```bash\n(.*?)```", TUTORIAL.read_text(), re.S)
    return [
        shlex.split(line.removeprefix(PREFIX))
        for block in blocks
        for line in block.splitlines()
        if line.startswith(PREFIX)
    ]


def biotope(root, *args):
    return subprocess.run([sys.executable, "-m", "biotope.cli", *args], cwd=root, text=True, capture_output=True)


def prepare(tmp_path):
    root = tmp_path / "project"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("__pycache__", ".biotope", "build"))
    sources = {path: path.read_bytes() for path in (root / "graph/sources").rglob("*.py")}
    for command in tutorial_commands():
        if command[0] != "graph":
            result = biotope(root, *command)
            assert result.returncode == 0, result.stdout + result.stderr
    assert {path: path.read_bytes() for path in (root / "graph/sources").rglob("*.py")} == sources
    assert len(list((root / ".biotope/contracts").iterdir())) == 2
    return root


def run(root, action="check", output=None):
    command = ["graph", action]
    if output:
        command += ["--out", "graph/build/" + output]
    return biotope(root, *command)
