import json
from pathlib import Path

from click.testing import CliRunner

from biotope.cli import cli


MANIFEST = ".biotope/datasets/data/study.jsonld"
PEOPLE = "push_people_csv_people"
GRAPH = {
    "topology/__init__.py": """
from biotope.graph import Topology

from .person.node import Person


TOPOLOGY = Topology(nodes=(Person,), edges=())
""",
    "topology/person/__init__.py": "",
    "topology/person/node.py": """
from dataclasses import dataclass
from typing import ClassVar, NewType


PersonId = NewType("PersonId", str)


@dataclass(frozen=True)
class Person:
    schema_id: ClassVar[str] = "study:person"
    id: PersonId
    name: str
""",
    "mappings/__init__.py": """
from biotope.graph import MappingEntry

from .person import MAPPING


MAPPINGS: tuple[MappingEntry, ...] = (MAPPING,)
""",
    "mappings/person/__init__.py": f"""
from collections.abc import Iterator

from biotope.graph import Mapping, SourceRecord

from ...sources.study.{PEOPLE}.schema import PushPeopleCsvPeople
from ...topology.person.node import Person, PersonId


def map_person(person: SourceRecord[PushPeopleCsvPeople]) -> Iterator[Person]:
    yield Person(id=PersonId(f"study:{{person.value.person_id}}"), name=person.value.name or "")


MAPPING = Mapping(name="study:person", function=map_person, evidence=("Synthetic people.",))
""",
    "pipelines/compose.py": f"""
from biotope.graph import RunContext

from ..mappings.person import MAPPING
from ..sources.study.{PEOPLE}.loader import load as load_people
from ..sources.study.report_html.loader import load as load_report


def run(context: RunContext) -> None:
    for person in load_people(context):
        context.map(MAPPING, person)
    for _ in load_report(context):
        pass
""",
    f"sources/study/{PEOPLE}/loader.py": """
import csv
from collections.abc import Iterator
from pathlib import Path

from biotope.graph import Evidence, RunContext, SourceRecord

from . import SOURCE
from .schema import PushPeopleCsvPeople


def _read(path: Path) -> Iterator[SourceRecord[PushPeopleCsvPeople]]:
    with path.open(newline="", encoding="utf-8") as stream:
        for line, row in enumerate(csv.DictReader(stream), start=2):
            record = PushPeopleCsvPeople(person_id=row["person_id"], name=row["name"])
            evidence = Evidence(path.as_posix(), "v1", PushPeopleCsvPeople.__record_set__, f"line {line}")
            yield SourceRecord(record, (evidence,))


def load(context: RunContext) -> Iterator[SourceRecord[PushPeopleCsvPeople]]:
    yield from context.load(SOURCE, _read, SOURCE.path())
""",
    "sources/study/report_html/loader.py": """
from collections.abc import Iterator
from pathlib import Path

from biotope.graph import Evidence, RunContext, SourceRecord

from . import SOURCE
from .schema import Facts


def _read(path: Path) -> Iterator[SourceRecord[Facts]]:
    path.read_text(encoding="utf-8")
    yield SourceRecord(Facts(), (Evidence(path.as_posix(), "v1", Facts.__record_set__, "body"),))


def load(context: RunContext) -> Iterator[SourceRecord[Facts]]:
    yield from context.load(SOURCE, _read, SOURCE.path())
""",
    "sources/__init__.py": f"""
from biotope.graph import SourceContract

from .inventory import INVENTORY
from .study.{PEOPLE} import SOURCE as PEOPLE
from .study.report_html import SOURCE as REPORT


SOURCES: tuple[SourceContract, ...] = (PEOPLE, REPORT)
EXCLUDED_SOURCES: dict[str, str] = {{
    source.name: "A new input; select it once its loader is written" for source in INVENTORY if source not in SOURCES
}}
""",
}


def invoke(*args):
    return CliRunner().invoke(cli, list(args))


def ok(*args):
    result = invoke(*args)
    assert result.exit_code == 0, result.output
    return result


def refresh(dataset="data/study"):
    ok("add", "--rebake", dataset)
    ok("source", "generate", MANIFEST, "--out", "graph/sources")


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
    for path, text in GRAPH.items():
        (root / "graph" / path).parent.mkdir(parents=True, exist_ok=True)
        (root / "graph" / path).write_text(text.lstrip())
    pipeline = root / "graph/pipelines/build_graph.py"
    text = pipeline.read_text().replace('name="",', 'name="study:people",')
    pipeline.write_text(text.replace('scope="",', 'scope="Synthetic people of one study.",'))
    assert built(root) == ({"data/study/push/people.csv", "data/study/docs/report.html"}, 2)
    return root
