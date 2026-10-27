import json
import shutil
from pathlib import Path

from click.testing import CliRunner

from biotope.cli import cli


MANIFEST = ".biotope/datasets/data/study.jsonld"
PEOPLE = "push_people_csv_people"
GRAPH = Path(__file__).resolve().parents[1] / "fixtures/study_graph"


def invoke(*args):
    return CliRunner().invoke(cli, list(args))


def ok(*args):
    result = invoke(*args)
    assert result.exit_code == 0, result.output
    return result


def refresh(*datasets):
    for dataset in datasets or ("data/study",):
        ok("add", "--rebake", dataset)
        ok("source", "generate", f".biotope/datasets/{dataset}.jsonld", "--out", "graph/sources")


def built(root: Path) -> tuple[set[str], int]:
    ok("graph", "check")
    ok("graph", "build")
    run = json.loads((root / "graph/build/run.json").read_text())
    read = {Path(artifact).resolve().relative_to(root.resolve()).as_posix() for artifact, _ in run["source_versions"]}
    return read, run["graph_objects"]["nodes"]


def findings(result) -> list[dict]:
    return json.loads(result.stdout)["findings"]


def buildable(tmp_path, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    root = tmp_path / "project"
    study = root / "data/study"
    (study / "push").mkdir(parents=True)
    (study / "docs").mkdir()
    (study / "push/people.csv").write_text("person_id,name\np1,Ada\np2,Grace\n")
    (study / "docs/report.html").write_text("<html><body>Report, first download</body></html>")
    monkeypatch.chdir(root)
    ok("init", ".", "--no-prompt")
    ok("add", "data/study")
    ok("graph", "scaffold")
    ok("source", "generate", MANIFEST, "--out", "graph/sources")
    shutil.copytree(GRAPH, root / "graph", dirs_exist_ok=True)
    pipeline = root / "graph/pipelines/build_graph.py"
    text = pipeline.read_text().replace('name="",', 'name="study:people",')
    pipeline.write_text(text.replace('scope="",', 'scope="Synthetic people of one study.",'))
    assert built(root) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)
    return root
