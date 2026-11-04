import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from biotope.cli import cli


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/extraction"


class Study:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run(self, *args: str):
        return CliRunner().invoke(cli, list(args))

    def extract(self, *args: str):
        result = CliRunner(mix_stderr=False).invoke(cli, ["extract", *args, "--json"])
        return result, json.loads(result.stdout)

    def edit(self, path: str, old: str, new: str) -> None:
        file = self.root / path
        text = file.read_text(encoding="utf-8")
        assert old in text, (path, old)
        file.write_text(text.replace(old, new, 1), encoding="utf-8")

    def records(self, name: str) -> list[dict]:
        lines = (self.root / "data/extracted" / f"{name}.jsonl").read_text().splitlines()
        return [json.loads(line) for line in lines]

    def snapshot(self) -> dict[str, bytes]:
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in sorted(self.root.rglob("*"))
            if path.is_file() and not {".git", "__pycache__"} & set(path.relative_to(self.root).parts)
        }


@pytest.fixture
def study(tmp_path, monkeypatch):
    for variable, value in (
        ("GIT_AUTHOR_NAME", "Test"),
        ("GIT_AUTHOR_EMAIL", "test@example.org"),
        ("GIT_COMMITTER_NAME", "Test"),
        ("GIT_COMMITTER_EMAIL", "test@example.org"),
        ("PROFILE_READER_KEY", "a key"),
        ("PYTHONDONTWRITEBYTECODE", "1"),
    ):
        monkeypatch.setenv(variable, value)
    monkeypatch.setattr("sys.dont_write_bytecode", True)
    root = tmp_path / "study"
    project = Study(root)
    created = project.run("init", "study", "--dir", str(tmp_path), "--no-prompt")
    assert created.exit_code == 0, created.output
    monkeypatch.chdir(root)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    assert project.run("graph", "scaffold").exit_code == 0
    (root / "data/pages").mkdir(parents=True)
    (root / "data/calls").mkdir(parents=True)
    for page in ("lind.html", "okafor.html"):
        shutil.copy(FIXTURES / page, root / "data/pages" / page)
    shutil.copy(FIXTURES / "call.md", root / "data/calls/call.md")
    shutil.copy(FIXTURES / "readers.py", root / "graph/extraction/readers.py")
    shutil.copy(FIXTURES / "extractions.py", root / "graph/extraction/__init__.py")
    added = project.run("add", "data/pages", "data/calls")
    assert added.exit_code == 0, added.output
    return project
