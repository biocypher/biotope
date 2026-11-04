import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import types
from dataclasses import fields, is_dataclass
from typing import Union, get_args, get_origin, get_type_hints

from conftest import FIXTURES

from biotope.extraction import Schema
from biotope.graph import Evidence, Pipeline, RunContext, SourceRecord, Topology


LIND = "data/pages/lind.html"
OKAFOR = "data/pages/okafor.html"
CALL = "data/calls/call.md"
READERS = "graph/extraction/readers.py"
LISTED = "graph/extraction/__init__.py"
VERSION = 'version = "1"\n    settings = {"heading": "h1"}'


def extraction(report, name="profile"):
    [found] = [item for item in report["extractions"] if item["name"] == name]
    return found


def statuses(report, name="profile"):
    return {document["path"]: document["status"] for document in extraction(report, name)["documents"]}


def described_fields(manifest):
    found = {}

    def collect(items):
        for item in items:
            found[item["@id"]] = item.get("description")
            collect(item.get("subField", []))

    collect(manifest["recordSet"][0]["field"])
    return found


def manifest(study, name="profile"):
    return json.loads((study.root / f".biotope/datasets/data/extracted/{name}.jsonl.jsonld").read_text())


def test_run_stores_every_listed_extraction_with_its_evidence_and_registers_it(study):
    (study.root / "data/pages/fetch.ksh").write_text("echo Mara Lind\n")
    assert study.run("add", "data/pages", "--rebake").exit_code == 0
    result, report = study.extract("run")
    assert result.exit_code == 0, result.output
    assert [item["name"] for item in report["extractions"]] == ["profile", "funding_round"]
    assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"}
    assert statuses(report, "funding_round") == {CALL: "extracted"}
    assert f"Extracting 1/2 {LIND}" in result.stderr and f"Extracting 2/2 {OKAFOR}" in result.stderr

    lind, okafor = study.records("profile")
    assert (lind["id"], lind["document"], okafor["id"]) == ("pages/lind.html", LIND, "pages/okafor.html")
    assert lind["values"]["name"] == {"value": "Mara Lind", "evidence": {"quote": "Dr. Mara Lind", "locator": None}}
    assert lind["values"]["group"]["evidence"] == {"quote": None, "locator": "the first strong text"}
    assert [item["value"] for item in lind["values"]["methods"]] == [
        "spatial transcriptomics",
        "single-cell RNA sequencing",
    ]
    profile = extraction(report)
    assert lind["provenance"] == {
        "document_sha256": profile["documents"][0]["sha256"],
        "schema": "Profile",
        "schema_revision": profile["schema"]["revision"],
        "extractor": {"name": "profile-reader", "version": "1", "settings": {"heading": "h1"}},
    }
    rounds = {record["id"]: record for record in study.records("funding_round")}
    assert sorted(rounds) == [
        'calls/call.md#round="Full proposal"',
        'calls/call.md#round="Pre-proposal"',
        'calls/call.md#round="Renewal"',
    ]
    full = rounds['calls/call.md#round="Full proposal"']["values"]
    assert full["budget"]["evidence"]["quote"] == "| Full proposal | 30 April 2027   | 1 500 000 EUR |"

    registered = manifest(study)
    assert registered["biotope:status"] == "processed"
    assert "creator" not in registered and "license" not in registered
    assert registered["prov:wasDerivedFrom"] == [{"@id": "data/pages"}]
    descriptions = described_fields(registered)
    prefix = "profile.jsonl#profile/values/name/evidence/"
    assert {key.removeprefix(prefix) for key in descriptions if key.startswith(prefix)} == {"quote", "locator"}
    assert descriptions["profile.jsonl#profile/values/name/value"] == (
        "The researcher's full name, without academic titles."
    )
    assert json.loads((study.root / ".biotope/extraction/profile.json").read_text())["files"] == [LIND, OKAFOR]
    tracked = [
        "data/extracted/profile.jsonl",
        ".biotope/datasets/data/extracted/profile.jsonl.jsonld",
        ".biotope/extraction/profile.json",
    ]
    assert subprocess.run(["git", "check-ignore", *tracked], cwd=study.root).returncode == 1


def test_run_reuses_records_until_an_input_changes_and_creates_the_extractor_only_when_needed(study, monkeypatch):
    assert study.extract("run", "profile")[0].exit_code == 0
    before = study.snapshot()
    result, report = study.extract("run", "profile")
    assert result.exit_code == 0 and statuses(report) == {LIND: "reused", OKAFOR: "reused"}
    assert study.snapshot() == before
    monkeypatch.chdir(study.root / "data")
    result, report = study.extract("run", "profile")
    assert result.exit_code == 0 and extraction(report)["output"] == "data/extracted/profile.jsonl"
    assert study.snapshot() == before
    monkeypatch.chdir(study.root)

    stored = study.records("profile")
    (study.root / "data/extracted/profile.jsonl").unlink()
    result, report = study.extract("run", "profile")
    assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"} and study.records("profile") == stored

    study.edit(OKAFOR, "tissue images", "stained tissue images")
    result, report = study.extract("run", "profile")
    assert statuses(report) == {LIND: "reused", OKAFOR: "extracted"}

    for old, new in (
        (VERSION, VERSION.replace('"1"', '"2"')),
        ('{"heading": "h1"}', '{"heading": "h2"}'),
        ("without academic titles", "as written"),
    ):
        study.edit(READERS, old, new)
        result, report = study.extract("run", "profile")
        assert result.exit_code == 0, result.output
        assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"}

    monkeypatch.delenv("PROFILE_READER_KEY")
    result, report = study.extract("run", "profile")
    assert result.exit_code == 0 and statuses(report) == {LIND: "reused", OKAFOR: "reused"}
    study.edit(LIND, "Spatial Atlas Group", "Spatial Atlas Lab")
    result, report = study.extract("run", "profile")
    assert result.exit_code != 0 and statuses(report) == {LIND: "failed", OKAFOR: "reused"}
    assert extraction(report)["documents"][0]["reason"] == "Set PROFILE_READER_KEY"
    assert [record["id"] for record in study.records("profile")] == ["pages/lind.html", "pages/okafor.html"]


def test_moving_a_dataset_keeps_record_ids_and_moving_records_is_refused(study):
    assert study.extract("run", "profile")[0].exit_code == 0
    stored = [record["id"] for record in study.records("profile")]
    moved = study.run("mv", "-r", "data/pages", "data/web/pages")
    assert moved.exit_code == 0, moved.output
    result, report = study.extract("run", "profile")
    assert result.exit_code == 0, result.output
    assert set(statuses(report).values()) == {"reused"}
    assert [record["id"] for record in study.records("profile")] == stored
    assert [record["document"] for record in study.records("profile")] == [
        "data/web/pages/lind.html",
        "data/web/pages/okafor.html",
    ]
    profile = extraction(report)
    assert (profile["moved"], profile["appeared"], profile["disappeared"]) == ([], [], [])

    before = study.snapshot()
    for move in (("data/extracted/profile.jsonl", "data/profile.jsonl"), ("-r", "data", "inputs")):
        refused = study.run("mv", *move)
        assert refused.exit_code != 0 and "rename the extraction" in " ".join(refused.output.split())
    assert study.snapshot() == before


def test_an_annotated_extracted_dataset_keeps_its_annotation_and_its_schema_descriptions(study):
    assert study.extract("run", "profile")[0].exit_code == 0
    given = ("description=Profiles of the researchers.", "url=https://example.org/profiles")
    annotated = study.run("annotate", "set", "data/extracted/profile.jsonl", *given)
    assert annotated.exit_code == 0, annotated.output
    annotation = study.root / "data/extracted/profile.jsonl.biotope.yaml"
    written = annotation.read_bytes()
    name = "profile.jsonl#profile/values/name/value"

    def described():
        data = manifest(study)
        return (data["description"], data["url"]), described_fields(data)[name]

    dataset = ("Profiles of the researchers.", "https://example.org/profiles")
    assert described() == (dataset, "The researcher's full name, without academic titles.")
    study.edit(READERS, "without academic titles", "as written")
    result, report = study.extract("run", "profile")
    assert result.exit_code == 0 and statuses(report) == {LIND: "extracted", OKAFOR: "extracted"}
    assert annotation.read_bytes() == written
    assert described() == (dataset, "The researcher's full name, as written.")


def test_record_ids_follow_the_record_key(study):
    assert study.extract("run", "funding_round")[0].exit_code == 0
    first = [record["id"] for record in study.records("funding_round")]
    pre = "| Pre-proposal  | 15 January 2027 | no funding    |\n"
    study.edit(CALL, pre, "")
    renewal = "| Renewal       | 1 March 2029    | 750 000 EUR   |\n"
    study.edit(CALL, renewal, f"{renewal}{pre}")
    result, report = study.extract("run", "funding_round")
    rounds = extraction(report, "funding_round")
    assert statuses(report, "funding_round") == {CALL: "extracted"}
    assert [record["id"] for record in study.records("funding_round")] == first
    assert (rounds["appeared"], rounds["disappeared"]) == ([], [])

    study.edit(CALL, "| Renewal       |", "| Extension     |")
    result, report = study.extract("run", "funding_round")
    assert result.exit_code == 0, result.output
    assert extraction(report, "funding_round")["disappeared"] == ['calls/call.md#round="Renewal"']
    assert extraction(report, "funding_round")["appeared"] == ['calls/call.md#round="Extension"']

    study.edit(CALL, pre, f"{pre}| Extension | 1 May 2030 | 1 EUR |\n")
    result, report = study.extract("run", "funding_round")
    assert result.exit_code != 0
    [document] = extraction(report, "funding_round")["documents"]
    assert document["status"] == "failed" and "round" in document["reason"]


def test_extraction_code_imports_project_helpers_and_values_are_validated(study):
    (study.root / "graph/extraction/numbers.py").write_text(
        "import re\n\n\ndef numbers(text: str) -> list[str]:\n    return re.findall(r'[0-9]+(?:[.][0-9]+)?', text)\n"
    )
    (study.root / "graph/extraction/readings.py").write_text(
        "import json\nfrom dataclasses import dataclass\nfrom typing import Any, ClassVar\n\n"
        "from biotope.extraction import Document, Extractor, Schema\n\nfrom .numbers import numbers\n\n\n"
        "@dataclass(frozen=True)\nclass Reading:\n    __record_key__: ClassVar[tuple[str, ...]] = ('number',)\n\n"
        "    number: float\n\n\nclass ReadingReader(Extractor):\n    name = 'readings'\n    version = '1'\n\n"
        "    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]:\n"
        "        text = document.path.read_text()\n"
        "        return [{'number': {'value': json.loads(found), 'quote': found}} for found in numbers(text)]\n"
    )
    study.edit(LISTED, "from .readers import", "from .readings import Reading, ReadingReader\nfrom .readers import")
    study.edit(
        LISTED,
        "\n)\n",
        '\n    Extraction(name="reading", schema=Reading, extractor=ReadingReader, files=("data/readings.txt",)),\n)\n',
    )
    ids = []
    for text in ("Readings: 1", "Readings: 1.0", "Readings: 1 and 1.0"):
        (study.root / "data/readings.txt").write_text(text)
        result, report = study.extract("try", "reading", "data/readings.txt")
        [document] = report["documents"]
        ids.append([record["id"] for record in document["records"]])
    assert ids[0] == ids[1] == ["data/readings.txt#number=1.0"]
    assert result.exit_code != 0 and document["status"] == "failed" and "number" in document["reason"]

    (study.root / "data/readings.txt").write_text("Readings: 2")
    result, report = study.extract("run", "reading")
    assert result.exit_code != 0 and "no dataset describes data/readings.txt" in report["error"]
    assert study.run("add", "data/readings.txt").exit_code == 0
    result, report = study.extract("run", "reading")
    assert result.exit_code == 0, result.output
    assert [record["id"] for record in study.records("reading")] == ["readings.txt#number=2.0"]


def test_failed_empty_and_removed_documents(study):
    study.edit(OKAFOR, "<main>", "<main><!-- fail -->")
    result, report = study.extract("run", "profile")
    assert result.exit_code != 0
    assert statuses(report) == {LIND: "extracted", OKAFOR: "failed"}
    assert extraction(report)["documents"][1]["reason"] == "the page is marked to fail"
    assert [record["id"] for record in study.records("profile")] == ["pages/lind.html"]

    study.edit(OKAFOR, "<main><!-- fail -->", "<main>")
    study.edit(OKAFOR, "<h1>Chidi Okafor</h1>", "")
    result, report = study.extract("run", "profile")
    assert result.exit_code == 0 and statuses(report) == {LIND: "reused", OKAFOR: "empty"}

    (study.root / "data/pages/new.html").write_text("<h1>Ada Byron</h1>")
    shutil.copy(study.root / LIND, study.root / "data/pages/copy.html")
    result, report = study.extract("run", "profile")
    assert result.exit_code != 0
    assert "no dataset describes data/pages/new.html; describe it with biotope add;" in report["error"]
    assert (
        "data/pages/copy.html is identical to data/pages/lind.html, and biotope add describes identical files "
        "once, so delete the copy, or narrow the extraction's file patterns"
    ) in report["error"]
    (study.root / "data/pages/new.html").unlink()
    (study.root / "data/pages/copy.html").unlink()
    (study.root / LIND).unlink()
    assert study.run("add", "data/pages", "--rebake").exit_code == 0
    result, report = study.extract("run", "profile")
    assert result.exit_code == 0, result.output
    assert extraction(report)["disappeared"] == ["pages/lind.html"] and statuses(report) == {OKAFOR: "reused"}
    assert study.records("profile") == []


def test_an_unreadable_document_fails_and_keeps_its_records(study):
    assert study.extract("run", "profile")[0].exit_code == 0
    kept = study.records("profile")
    (study.root / LIND).chmod(0)
    try:
        result, report = study.extract("run", "profile")
    finally:
        (study.root / LIND).chmod(0o644)
    assert result.exit_code != 0 and statuses(report) == {LIND: "failed", OKAFOR: "reused"}
    assert extraction(report)["documents"][0]["reason"].startswith("PermissionError")
    assert study.records("profile") == kept


def test_documents_of_datasets_with_one_name_are_refused(study):
    for year in ("y2024", "y2025"):
        (study.root / "data" / year).mkdir()
        shutil.copy(study.root / CALL, study.root / "data" / year / "call.md")
        assert study.run("add", f"data/{year}/call.md").exit_code == 0
    study.edit(LISTED, 'files=("data/calls/*.md",)', 'files=("data/*/call.md",)')
    result, report = study.extract("run", "funding_round")
    assert result.exit_code != 0
    assert "data/y2024/call.md, data/y2025/call.md would share the record path call.md" in report["error"]
    assert "give the datasets different names" in report["error"]


def test_an_interrupted_run_keeps_the_records_and_a_rerun_completes_it(study, monkeypatch):
    assert study.extract("run", "profile")[0].exit_code == 0
    stored = (study.root / "data/extracted/profile.jsonl").read_bytes()
    study.edit(READERS, VERSION, VERSION.replace('"1"', '"2"'))
    replace = os.replace

    def interrupted(source, target):
        if str(target).endswith("profile.jsonl"):
            raise OSError("interrupted")
        replace(source, target)

    monkeypatch.setattr(os, "replace", interrupted)
    assert study.run("extract", "run", "profile").exit_code != 0
    monkeypatch.setattr(os, "replace", replace)
    assert (study.root / "data/extracted/profile.jsonl").read_bytes() == stored
    progress = study.root / ".biotope/progress/profile.jsonl"
    assert len(progress.read_text().splitlines()) == 2
    assert subprocess.run(["git", "check-ignore", "-q", str(progress)], cwd=study.root).returncode == 0

    monkeypatch.delenv("PROFILE_READER_KEY")
    result, report = study.extract("run", "profile")
    assert result.exit_code == 0 and statuses(report) == {LIND: "reused", OKAFOR: "reused"}
    assert not progress.exists()
    assert {record["provenance"]["extractor"]["version"] for record in study.records("profile")} == {"2"}
    [entry] = [
        item for item in manifest(study)["distribution"] if item.get("contentUrl") == "data/extracted/profile.jsonl"
    ]
    assert entry["sha256"] == hashlib.sha256((study.root / "data/extracted/profile.jsonl").read_bytes()).hexdigest()


def test_generated_sources_load_extracted_records_and_skip_extracted_documents(study, monkeypatch):
    (study.root / "data/pages/notes.txt").write_text("Visiting hours.\n")
    assert study.run("add", "data/pages", "--rebake").exit_code == 0
    assert study.extract("run", "profile")[0].exit_code == 0
    for described in (".biotope/datasets/data/pages.jsonld", ".biotope/datasets/data/extracted/profile.jsonl.jsonld"):
        generated = study.run("source", "generate", described, "--out", "graph/sources")
        assert generated.exit_code == 0, generated.output
    packages = sorted(path.name for path in (study.root / "graph/sources/pages").iterdir() if path.is_dir())
    assert packages == ["notes_txt"]
    checked = study.run("graph", "check", "--json")
    assert not [item for item in json.loads(checked.output)["findings"] if item["code"] == "inventory.stale"]

    monkeypatch.syspath_prepend(str(study.root))
    package = next((study.root / "graph/sources/profile_jsonl").rglob("schema.py")).parent.relative_to(study.root)
    try:
        source = importlib.import_module(".".join(package.parts)).SOURCE
        [record_class] = source.records
        rows = [
            SourceRecord(
                decoded(record_class, line),
                (Evidence(line["document"], "v1", record_class.__record_set__, line["id"]),),
            )
            for line in study.records("profile")
        ]
        context = RunContext(Pipeline("extracted", Topology((), ()), (source,), (), lambda _: None, "test", ()))
        assert list(context.load(source, lambda _: iter(rows), None)) == rows
    finally:
        for name in [name for name in sys.modules if name == "graph" or name.startswith("graph.")]:
            del sys.modules[name]


def decoded(cls, value):
    if isinstance(value, list):
        return [decoded(cls, item) for item in value]
    if not is_dataclass(cls) or not isinstance(value, dict):
        return value
    hints = get_type_hints(cls)
    kwargs = {}
    for item in fields(cls):
        annotation = hints[item.name]
        while get_origin(annotation) in (Union, types.UnionType, list):
            annotation = next(arg for arg in get_args(annotation) if arg is not type(None))
        kwargs[item.name] = decoded(annotation, value.get(item.name))
    return cls(**kwargs)


def test_generation_follows_the_documents_an_extraction_has_read(study):
    def generated():
        result = study.run("source", "generate", ".biotope/datasets/data/pages.jsonld", "--out", "graph/sources")
        assert result.exit_code == 0, result.output
        folder = study.root / "graph/sources/pages"
        names = sorted(path.name for path in folder.iterdir() if path.is_dir()) if folder.is_dir() else []
        return names, " ".join(result.output.split())

    assert generated()[0] == ["lind_html", "okafor_html"]
    assert study.extract("run")[0].exit_code == 0
    packages, shown = generated()
    assert "'lind.html' is read by an extraction, whose records are mapped instead" in shown
    for package in packages:
        shutil.rmtree(study.root / "graph/sources/pages" / package)
    assert generated()[0] == []

    listed = (study.root / LISTED).read_text().splitlines(keepends=True)
    (study.root / LISTED).write_text("".join(line for line in listed if 'name="profile"' not in line))
    removed = study.run("rm", "-f", "data/extracted/profile.jsonl")
    assert removed.exit_code == 0, removed.output
    assert not (study.root / ".biotope/extraction/profile.json").exists()
    assert generated()[0] == ["lind_html", "okafor_html"]


def test_try_shows_records_and_changes_nothing(study):
    (study.root / "data/draft.html").write_text("<h1>Dr. Ada Byron</h1>")
    before = study.snapshot()
    result = study.run("extract", "try", "profile", LIND, OKAFOR, "data/draft.html")
    assert result.exit_code == 0, result.output
    for shown in ("Mara Lind", '"Dr. Mara Lind"', "at the first strong text", "single-cell RNA sequencing"):
        assert shown in result.output
    rounds, report = study.extract("try", "funding_round", CALL)
    assert rounds.exit_code == 0 and f"Extracting 1/1 {CALL}" in rounds.stderr
    [document] = report["documents"]
    assert 'calls/call.md#round="Renewal"' in {record["id"] for record in document["records"]}
    assert study.snapshot() == before


def test_the_schema_revision_covers_only_the_schema_and_unsupported_types_are_refused(study, tmp_path, monkeypatch):
    source = (FIXTURES / "readers.py").read_text()
    monkeypatch.syspath_prepend(str(tmp_path))

    def revision(text):
        module = tmp_path / f"variant_{len(list(tmp_path.glob('variant_*.py')))}.py"
        module.write_text(text)
        return Schema.from_class(importlib.import_module(module.stem).Profile).revision

    first = revision(source)
    assert revision(source.replace('version = "1"', 'version = "2"')) == first
    changed = {
        revision(source.replace("without academic titles", "as the page writes it")),
        revision(source.replace("    group: str | None", "    group: str")),
        revision(source.replace("A researcher's profile page", "A profile page")),
        revision(source.replace("    name: str = field(", "    full_name: str = field(")),
    }
    assert len(changed | {first}) == 5

    methods = "    methods: list[str] = field("
    for annotation in (
        "dict[str, str]",
        "tuple[int, int]",
        "set[str]",
        "list[str] | None",
        "int | str",
        "list[list[str]]",
    ):
        study.edit(READERS, methods, f"    links: {annotation}\n{methods}")
        result, report = study.extract("run", "profile")
        assert result.exit_code != 0 and "links" in report["error"], annotation
        study.edit(READERS, f"    links: {annotation}\n", "")
    study.edit(READERS, '("round",)', '("missing",)')
    result, report = study.extract("run", "funding_round")
    assert result.exit_code != 0 and "missing" in report["error"]


def test_the_extraction_list_is_checked_when_it_loads(study):
    before = study.snapshot()
    for path, old, new, message in (
        (READERS, f"    {VERSION}", '    settings = {"heading": "h1"}', "ProfileReader.version"),
        (LISTED, 'files=("data/calls/*.md",)', 'files=("../calls/*.md",)', "relative to the project root"),
        (LISTED, 'name="funding_round"', 'name="Funding round"', "lowercase letters"),
        (LISTED, "parallel=2", "parallel=0", "parallel"),
        (
            LISTED,
            'files=("data/calls/*.md",)',
            'files=("data/call/*.md",)',
            "funding_round: data/call/*.md matches no file",
        ),
        (READERS, '"heading": "h1"', '"heading": {"h1"}', "ProfileReader.settings must hold only JSON values"),
        (LISTED, 'name="profile"', 'name="funding_round"', "more than once"),
    ):
        study.edit(path, old, new)
        result, report = study.extract("run")
        assert result.exit_code != 0 and message in report["error"], message
        study.edit(path, new, old)
    result, report = study.extract("run", "missing")
    assert result.exit_code != 0 and "lists no extraction missing; it lists profile, funding_round" in report["error"]
    broken = study.root / ".biotope/datasets/broken.jsonld"
    broken.write_text("{")
    result, report = study.extract("run")
    assert result.exit_code != 0 and "broken.jsonld" in report["error"]
    broken.unlink()
    assert study.snapshot() == before
    result, report = study.extract("run", "funding_round")
    assert result.exit_code == 0 and [item["name"] for item in report["extractions"]] == ["funding_round"]


def test_a_listed_placeholder_is_refused_and_an_unlisted_one_is_ignored(study):
    template = "graph/extraction/template.py"
    assert (study.root / template).read_text().startswith("# biotope:placeholder\n")
    pipeline = study.root / "graph/pipelines/build_graph.py"
    pipeline.write_text(pipeline.read_text().replace('name="",', 'name="pages",').replace('scope="",', 'scope="none",'))

    def placeholders():
        checked = study.run("graph", "check", "--json")
        findings = json.loads(checked.output)["findings"]
        assert not [finding for finding in findings if finding["code"].startswith("python.")], findings
        return [finding["location"]["path"] for finding in findings if finding["code"] == "extraction.placeholder"]

    assert placeholders() == []
    assert study.extract("run")[0].exit_code == 0

    study.edit(LISTED, "from .readers import", "from .template import Record, RecordExtractor\nfrom .readers import")
    listed = 'Extraction(name="record", schema=Record, extractor=RecordExtractor, files=("data/calls/*.md",)),\n'
    study.edit(
        LISTED, "EXTRACTIONS: tuple[Extraction, ...] = (\n", f"EXTRACTIONS: tuple[Extraction, ...] = (\n    {listed}"
    )
    before = study.snapshot()
    for command in (("run",), ("run", "record"), ("try", "record", CALL)):
        result, report = study.extract(*command)
        assert result.exit_code != 0 and f"record: {template} is still a placeholder" in report["error"], command
    assert study.snapshot() == before
    assert [path.endswith(template) for path in placeholders()] == [True]


ROW_READER = """

class RowReader(Extractor):
    name = "row-reader"
    version = "1"

    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]:
        with document.path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        return [
            {key: {"value": value, "locator": f"row {n}"} for key, value in row.items()}
            for n, row in enumerate(rows, 1)
        ]
"""


def test_an_extraction_reads_the_rows_of_a_file_described_as_a_table(study):
    (study.root / "data/calls/rounds.csv").write_text("round,deadline,budget\nRenewal,1 March 2029,750 000 EUR\n")
    assert study.run("add", "data/calls", "--rebake").exit_code == 0
    study.edit(READERS, "import os\n", "import csv\nimport os\n")
    (study.root / READERS).write_text((study.root / READERS).read_text() + ROW_READER)
    study.edit(LISTED, "RoundReader\n", "RoundReader, RowReader\n")
    listed = 'Extraction(name="table_round", schema=FundingRound, extractor=RowReader, files=("data/calls/*.csv",)),\n'
    study.edit(
        LISTED, "EXTRACTIONS: tuple[Extraction, ...] = (\n", f"EXTRACTIONS: tuple[Extraction, ...] = (\n    {listed}"
    )

    result, report = study.extract("run")
    assert result.exit_code == 0, result.output
    assert statuses(report, "table_round") == {"data/calls/rounds.csv": "extracted"}
    [record] = study.records("table_round")
    assert record["id"] == 'calls/rounds.csv#round="Renewal"'
    assert record["values"]["budget"] == {"value": "750 000 EUR", "evidence": {"quote": None, "locator": "row 1"}}
    generated = study.run("source", "generate", ".biotope/datasets/data/calls.jsonld", "--out", "graph/sources")
    assert generated.exit_code == 0, generated.output
    packages = [path.name for path in (study.root / "graph/sources/calls").iterdir() if path.is_dir()]
    assert [name for name in packages if name.startswith("rounds")] and not [
        n for n in packages if n.startswith("call_")
    ]


def test_parallel_extraction_changes_neither_output_nor_report(study):
    outcomes = []
    for old, new in (("parallel=2", "parallel=1"), ("parallel=1", "parallel=3")):
        study.edit(LISTED, old, new)
        for stored in ("data/extracted", ".biotope/extraction", ".biotope/datasets/data/extracted"):
            shutil.rmtree(study.root / stored, ignore_errors=True)
        result, report = study.extract("run", "profile")
        assert result.exit_code == 0, result.output
        tried, attempt = study.extract("try", "profile", LIND, OKAFOR)
        outcomes.append((study.records("profile"), report, result.stderr, attempt, tried.stderr))
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][2].index(f"Extracting 1/2 {LIND}") < outcomes[0][2].index(f"Extracting 2/2 {OKAFOR}")


def test_redo_extracts_chosen_documents_again(study):
    assert study.extract("run")[0].exit_code == 0
    result, report = study.extract("run", "--redo", LIND)
    assert result.exit_code == 0, result.output
    assert statuses(report) == {LIND: "extracted", OKAFOR: "reused"}
    assert statuses(report, "funding_round") == {CALL: "reused"}
    lind, okafor = study.records("profile")
    assert lind["provenance"]["redone"] is True and "redone" not in okafor["provenance"]

    before = study.snapshot()
    result, report = study.extract("run", "profile")
    assert statuses(report) == {LIND: "reused", OKAFOR: "reused"} and study.snapshot() == before
    result, report = study.extract("run", "profile", "--redo", CALL)
    assert result.exit_code != 0 and CALL in report["error"] and study.snapshot() == before


def test_run_warns_when_git_ignores_its_output(study):
    with (study.root / ".gitignore").open("a") as ignore:
        ignore.write("\nextracted/\n")
    result, report = study.extract("run", "profile")
    assert result.exit_code == 0, result.output
    assert extraction(report)["ignored"] == [
        ".biotope/datasets/data/extracted/profile.jsonl.jsonld",
        "data/extracted/profile.jsonl",
    ]
    shown = study.run("extract", "run", "profile")
    assert "git ignores data/extracted/profile.jsonl" in " ".join(shown.output.split())


def test_extraction_code_is_graph_code_and_records_stay_out_of_a_folder_dataset(study):
    assert study.extract("run", "profile")[0].exit_code == 0
    pipeline = study.root / "graph/pipelines/build_graph.py"
    pipeline.write_text(pipeline.read_text().replace('name="",', 'name="pages",').replace('scope="",', 'scope="none",'))
    compose = study.root / "graph/pipelines/compose.py"
    compose.write_text(
        compose.read_text().replace("    raise NotImplementedError(", "    return\n    raise NotImplementedError(")
    )
    built = study.run("graph", "build")
    assert built.exit_code == 0, built.output
    run = json.loads((study.root / "graph/build/run.json").read_text())
    assert str((study.root / READERS).resolve()) in run["definitions"]["code_digests"]
    (study.root / READERS).write_text((study.root / READERS).read_text() + '\nWRONG: int = "text"\n')
    checked = study.run("graph", "check", "--json")
    assert checked.exit_code != 0
    assert any(
        finding["code"].startswith("python.") and finding["location"]["path"].endswith(READERS)
        for finding in json.loads(checked.output)["findings"]
    )

    (study.root / "data/extracted/profile.csv").write_text("name\nMara Lind\n")
    assert study.run("add", "data/extracted").exit_code == 0
    folder = json.loads((study.root / ".biotope/datasets/data/extracted.jsonld").read_text())
    identities = {entry["@id"] for entry in folder["distribution"]}
    assert "profile.csv" in identities and "profile.jsonl" not in identities
