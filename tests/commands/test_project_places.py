import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from biotope.cli import cli


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
GIT = shutil.which("git") or "git"
USER, EMAIL = "Ada Host", "ada@host.example"
HOST_IGNORE = "/data/**\n!/data/**/\n!/data/**/*.biotope.yaml\n!/data/extracted/**\n__pycache__/\n"
PROFILE = "graph/extraction/profile.py:Profile"
NOT_GIVEN = (USER, EMAIL, "Dataset Creator", "creator@example.com", "creativecommons.org/licenses/by")


@pytest.fixture(autouse=True)
def _no_global_git_config(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(root, *args):
    return subprocess.run([GIT, *args], cwd=root, capture_output=True, text=True, check=True).stdout


def invoke(*args):
    return CliRunner().invoke(cli, list(args))


def data(root):
    study = root / "data/raw/study"
    (study / "push").mkdir(parents=True)
    (study / "docs").mkdir()
    (study / "push/people.csv").write_text("person_id,name\np1,Ada\np2,Grace\n")
    (study / "docs/report.html").write_text("<html><body>Report</body></html>")
    (root / "data/raw/samples.csv").write_text("sample_id,person_id\ns1,p1\n")
    (root / "data/pages").mkdir()
    for page in ("lind.html", "okafor.html"):
        shutil.copy(FIXTURES / "extraction" / page, root / "data/pages" / page)


def host(root):
    (root / "src").mkdir(parents=True)
    (root / "src/app.py").write_text("print('host')\n")
    (root / "README.md").write_text("# Host\n")
    (root / ".gitignore").write_text(HOST_IGNORE)
    data(root)
    git(root, "init", "-q")
    for key, value in (("user.name", USER), ("user.email", EMAIL), ("commit.gpgsign", "false")):
        git(root, "config", key, value)
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "host")
    (root / "src/app.py").write_text("print('staged')\n")
    (root / "src/new.py").write_text("NEW = 1\n")
    git(root, "add", "src")
    (root / "README.md").write_text("# Host, unstaged\n")


def configure(root):
    path = root / ".biotope/config.yaml"
    config = yaml.safe_load(path.read_text())
    rules = FIXTURES / "extraction/rules.py"
    config["extraction"] = {"extractor": f"{rules}:LineExtractor", "version": "1", "line": 1}
    path.write_text(yaml.safe_dump(config, sort_keys=False))


def author_graph(root):
    shutil.copytree(FIXTURES / "study_graph", root / "graph", dirs_exist_ok=True)
    pipeline = root / "graph/pipelines/build_graph.py"
    text = pipeline.read_text().replace('name="",', 'name="host:people",')
    pipeline.write_text(text.replace('scope="",', 'scope="Synthetic people of the host.",'))
    shutil.copy(FIXTURES / "extraction/schemas.py", root / "graph/extraction/profile.py")


def steps(root):
    yield ("init", ".", "--no-prompt"), ()
    configure(root)
    yield ("add", "data/raw/study", "data/raw/samples.csv", "data/pages"), ()
    yield ("annotate", "set", "data/raw/study", "description=People who work at the host."), ()
    yield ("graph", "scaffold"), ()
    yield ("source", "generate", ".biotope/datasets/data/raw/study.jsonld", "--out", "graph/sources"), ()
    author_graph(root)
    yield ("graph", "check"), ()
    yield ("graph", "build"), ()
    yield ("graph", "metagraph"), ()
    yield ("extract", "run", PROFILE, "data/pages"), ()
    moved = ("data/raw/study/push/people.csv", "data/raw/study/push/staff.csv")
    yield ("mv", *moved), moved
    yield ("rm", "-f", "data/raw/samples.csv"), ("data/raw/samples.csv",)


def snapshot(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).parts[0] != ".git"
    }


def in_places(path):
    return path.startswith((".biotope/", "graph/", "data/extracted/")) or path.endswith(".biotope.yaml")


def repository(root):
    return git(root, "rev-list", "--all"), git(root, "for-each-ref"), git(root, "ls-files", "--stage")


def test_commands_write_only_in_their_places_and_never_to_git(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    root = tmp_path / "host"
    host(root)
    monkeypatch.chdir(root)
    state = repository(root)
    written: dict[str, bytes] = {}
    for args, named in steps(root):
        before = snapshot(root)
        result = invoke(*args)
        assert result.exit_code == 0, (args, result.output)
        after = snapshot(root)
        changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
        assert {path for path in changed if not in_places(path)} <= set(named), args
        assert (root / ".gitignore").read_text() == HOST_IGNORE
        assert repository(root) == state, args
        written.update({path: after[path] for path in changed if path in after and path not in named})
    assert git(root, "check-ignore", "graph/build/", "graph/metagraph.html").split() == [
        "graph/build/",
        "graph/metagraph.html",
    ]
    assert not any(value.encode() in content for content in written.values() for value in NOT_GIVEN)
    manifests = [json.loads(path.read_text()) for path in (root / ".biotope/datasets").rglob("*.jsonld")]
    assert len(manifests) == 3
    assert not any({"creator", "license"} & set(manifest) for manifest in manifests)


def test_init_creates_no_repository_and_keeps_project_yaml_in_biotope(tmp_path):
    result = invoke("init", "plain", "--dir", str(tmp_path), "--no-prompt")
    assert result.exit_code == 0, result.output
    root = tmp_path / "plain"
    assert (root / ".biotope/project.yaml").is_file()
    assert not (root / "project.yaml").exists() and not (root / ".git").exists()
    for retired in ("--visible", "--no-git"):
        refused = invoke("init", "other", "--dir", str(tmp_path), "--no-prompt", retired)
        assert refused.exit_code != 0 and "No such option" in refused.output


def test_init_gitignore_keeps_annotations_and_records_and_ignores_data(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    assert invoke("init", "fresh", "--dir", str(tmp_path), "--no-prompt").exit_code == 0
    root = tmp_path / "fresh"
    monkeypatch.chdir(root)
    git(root, "init", "-q")
    data(root)
    configure(root)
    assert invoke("add", "data/raw/study", "data/raw/samples.csv", "data/pages").exit_code == 0
    (root / "data/raw/samples.csv.biotope.yaml").write_text("description: Samples.\n")
    assert invoke("graph", "scaffold").exit_code == 0
    shutil.copy(FIXTURES / "extraction/schemas.py", root / "graph/extraction/profile.py")
    extracted = invoke("extract", "run", PROFILE, "data/pages")
    assert extracted.exit_code == 0, extracted.output
    for path in ("__pycache__/cache.cpython-312.pyc", "src/module.pyc", ".venv/bin/python"):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text("")
    kept = git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    assert {path for path in kept if path.startswith("data/")} == {
        "data/raw/study/.biotope.yaml",
        "data/pages/.biotope.yaml",
        "data/raw/samples.csv.biotope.yaml",
        "data/extracted/profile.jsonl",
    }
    ignored = ["data/raw/study/push/people.csv", "data/raw/samples.csv", "data/pages/lind.html"]
    ignored += ["__pycache__/cache.cpython-312.pyc", "src/module.pyc", ".venv/bin/python"]
    assert sorted(git(root, "check-ignore", *ignored).split()) == sorted(ignored)


def without_git(tmp_path):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    node = shutil.which("node")
    if node is not None:
        (binaries / "node").symlink_to(node)
    return str(binaries)


def test_commands_and_status_run_without_git(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    root = tmp_path / "host"
    host(root)
    monkeypatch.chdir(root)
    monkeypatch.setenv("PATH", without_git(tmp_path))
    assert shutil.which("git") is None
    for args, _ in steps(root):
        result = invoke(*args)
        assert result.exit_code == 0, (args, result.output)
    for retired in ("commit", "log", "push", "pull"):
        refused = invoke(retired)
        assert refused.exit_code != 0 and "No such command" in refused.output
    for retired in ("--porcelain", "--biotope-only"):
        refused = invoke("status", retired)
        assert refused.exit_code != 0 and "No such option" in refused.output
    listed = invoke("status")
    assert listed.exit_code == 0, listed.output
    manifests = ("data/extracted/profile", "data/pages", "data/raw/study")
    assert all(manifest in listed.output for manifest in manifests)
    assert "Changed" not in listed.output
    schema = next((root / "graph/sources/study").rglob("schema.py"))
    pinned = re.search(r'__source_digest__: ClassVar\[str\] = "(\w+)"', schema.read_text()).group(1)
    schema.write_text(schema.read_text().replace(pinned, "0" * 64))
    changed = invoke("status")
    assert changed.exit_code == 0, changed.output
    marked = [line for line in changed.output.splitlines() if line.startswith("Changed")]
    assert len(marked) == 1 and "data/raw/study" in marked[0]


def ignoring_project(root, repository):
    if repository:
        git(root, "init", "-q")
        (root / ".gitignore").write_text("/.biotope/\n/data/\n")
    assert invoke("init", ".", "--no-prompt").exit_code == 0
    shutil.copytree(FIXTURES / "things", root / "data/things")
    (root / "data/pages").mkdir()
    shutil.copy(FIXTURES / "extraction/lind.html", root / "data/pages/lind.html")
    (root / "graph/extraction").mkdir(parents=True)
    shutil.copy(FIXTURES / "extraction/schemas.py", root / "graph/extraction/profile.py")
    configure(root)


def warnings_of():
    contract = ".biotope/contracts/"
    manifest = ".biotope/datasets/data/things.jsonld"
    pages = [".biotope/datasets/data/pages.jsonld", "data/pages/.biotope.yaml"]
    yield ("add", "data/things", "data/pages"), [manifest, "data/things/.biotope.yaml", *pages]
    yield ("annotate", "set", "data/things", "description=Two tables."), [manifest, "data/things/.biotope.yaml"]
    yield ("source", "generate", manifest, "--out", "graph/sources"), [contract]
    yield ("mark", "data/things", "mapped"), [manifest]
    records = ["data/extracted/profile.jsonl", ".biotope/datasets/data/extracted/profile.jsonl.jsonld"]
    yield ("extract", "run", PROFILE, "data/pages"), [*records, ".biotope/extraction/data/extracted/profile.jsonl.json"]
    yield ("mv", "data/things/first.csv", "data/things/renamed.csv"), [manifest]
    yield ("rm", "-f", "data/things/second.csv"), [manifest]


def test_writers_warn_when_git_ignores_what_they_write(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for repository in (True, False):
        root = tmp_path / ("repository" if repository else "plain")
        root.mkdir()
        monkeypatch.chdir(root)
        ignoring_project(root, repository)
        rules = (root / ".gitignore").read_bytes()
        for args, expected in warnings_of():
            result = invoke(*args)
            assert result.exit_code == 0, (args, result.output)
            shown = " ".join(result.output.split())
            if not repository:
                assert "git ignores" not in shown, args
                continue
            warned = re.findall(r"git ignores (\S+?)\.? Commit", shown)
            assert len(warned) == len(set(warned)), (args, warned)
            for path in expected:
                assert any(item.startswith(path) for item in warned), (args, path, result.output)
            assert (root / ".gitignore").read_bytes() == rules
        if repository:
            assert (
                subprocess.run([GIT, "check-ignore", ".biotope/datasets/data/things.jsonld"], cwd=root).returncode == 0
            )
