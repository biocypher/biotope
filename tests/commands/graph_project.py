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


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def findings(result) -> list[dict]:
    return json.loads(result.stdout)["findings"]


def buildable(tmp_path, monkeypatch, people="data/study/push/people.csv"):
    monkeypatch.setenv("COLUMNS", "300")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    root = tmp_path / "project"
    study = root / "data/study"
    (study / "docs").mkdir(parents=True)
    (root / people).parent.mkdir(parents=True, exist_ok=True)
    (root / people).write_text("person_id,name\np1,Ada\np2,Grace\n")
    (study / "docs/report.html").write_text("<html><body>Report, first download</body></html>")
    monkeypatch.chdir(root)
    datasets = ["data/study"] if people.startswith("data/study/") else ["data/study", people]
    ok("init", ".", "--no-prompt")
    ok("add", *datasets)
    ok("graph", "scaffold")
    for dataset in datasets:
        ok("source", "generate", f".biotope/datasets/{dataset}.jsonld", "--out", "graph/sources")
    shutil.copytree(GRAPH, root / "graph", dirs_exist_ok=True)
    if people != "data/study/push/people.csv":
        _read_people_from_its_own_dataset(root / "graph")
    pipeline = root / "graph/pipelines/build_graph.py"
    text = pipeline.read_text().replace('name="",', 'name="study:people",')
    pipeline.write_text(text.replace('scope="",', 'scope="Synthetic people of one study.",'))
    assert built(root) == ({people, "data/study/docs/report.html"}, 2)
    return root


def _read_people_from_its_own_dataset(graph: Path) -> None:
    loader = graph / "sources/study/push_people_csv_people/loader.py"
    loader.replace(graph / "sources/people_csv/people_csv_people/loader.py")
    loader.parent.rmdir()
    for module in graph.rglob("*.py"):
        text = module.read_text()
        renamed = text.replace("study.push_people_csv_people", "people_csv.people_csv_people")
        module.write_text(renamed.replace("PushPeopleCsvPeople", "PeopleCsvPeople"))
