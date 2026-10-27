import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import types
from dataclasses import fields, is_dataclass
from typing import Union, get_args, get_origin, get_type_hints

import pytest
from conftest import FIXTURES, KEY, LIVE_KEY, ROUNDS, ROWS, funding_round, quoted
from conftest import LIND as LIND_ANSWER
from conftest import OKAFOR as OKAFOR_ANSWER

from biotope.extraction import Schema, llm
from biotope.extraction import text as converter
from biotope.graph import Evidence, Pipeline, RunContext, SourceRecord, Topology


PROFILE = "graph/extraction/schemas.py:Profile"
ROUND = "graph/extraction/schemas.py:FundingRound"
LIND = "data/pages/lind.html"
OKAFOR = "data/pages/okafor.html"
CALL = "data/calls/call.pdf"
REPORT = "data/reports/report.pdf"
SUMMARY = "data/calls/summary.txt"


def squeeze(text):
    return re.sub(r"[\s\-‐-―−­]+", "", text).lower()


def statuses(report):
    return {document["path"]: document["status"] for document in report["documents"]}


def test_run_stores_records_with_evidence_and_registers_them(study):
    (study.root / "data/pages/fetch.ksh").write_text("echo Mara Lind\n")
    assert study.run("add", "data/pages", "--rebake").exit_code == 0
    answer = json.loads(json.dumps(OKAFOR_ANSWER))
    answer["record"]["methods"].append({"value": "tissue imaging"})
    study.endpoint.reply("Chidi Okafor", answer)
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"}
    assert len(study.endpoint.requests) == 2
    assert f"Extracting 1/2 {LIND}" in result.stderr and f"Extracting 2/2 {OKAFOR}" in result.stderr
    requested = study.endpoint.requests[0]["body"]["response_format"]["json_schema"]["schema"]
    assert list(requested["properties"]) == ["record"]
    lind, okafor = study.records("profile")
    assert (lind["id"], lind["document"], okafor["id"]) == (LIND, LIND, OKAFOR)
    assert lind["values"]["name"]["value"] == "Mara Lind"
    assert [item["value"] for item in lind["values"]["methods"]] == [
        "spatial transcriptomics",
        "single-cell RNA sequencing",
    ]
    provenance = lind["provenance"]
    assert provenance["document_sha256"] == report["documents"][0]["sha256"]
    assert provenance["schema"] == "Profile"
    assert provenance["schema_revision"] == report["schema"]["revision"]
    assert provenance["extractor"] == {
        "name": "llm",
        "version": report["extractor"]["version"],
        "settings": {"endpoint": study.endpoint.url, "model": "test/model"},
    }
    for record in (lind, okafor):
        text = study.text(record["document"])
        values = record["values"]
        for value in [values["name"], values["group"], *values["methods"]]:
            evidence = value["evidence"]
            if evidence and evidence["aligned"]:
                assert squeeze(text[evidence["start"] : evidence["end"]]) == squeeze(evidence["quote"])
                assert evidence["page"] is None
    unaligned = okafor["values"]["group"]
    assert unaligned["value"] == "Machine Learning for Tissues Group"
    assert unaligned["evidence"]["aligned"] is False and unaligned["evidence"]["start"] is None
    assert okafor["values"]["methods"][1] == {"value": "tissue imaging", "evidence": None}
    assert report["unaligned"] == [
        {"record": OKAFOR, "field": "group", "quote": "Machine Learning for Tissues Lab"},
        {"record": OKAFOR, "field": "methods", "quote": None},
    ]
    shown = study.run("extract", "run", PROFILE, "data/pages")
    assert shown.exit_code == 0 and "methods: no quote or locator" in shown.output
    tried = study.run("extract", "try", PROFILE, OKAFOR)
    assert tried.exit_code == 0 and re.search(r'methods: "tissue imaging"\s+no quote or locator', tried.output)
    assert sorted(report["appeared"]) == [LIND, OKAFOR] and report["disappeared"] == []

    result, report = study.extract("run", ROUND, "data/calls")
    assert result.exit_code == 0, result.output
    requested = study.endpoint.requests[-1]["body"]["response_format"]["json_schema"]["schema"]
    assert list(requested["properties"]) == ["records"]
    rounds = {record["id"]: record for record in study.records("funding_round")}
    full = rounds['data/calls/call.pdf#round="Full proposal"']
    evidence = full["values"]["deadline"]["evidence"]
    assert evidence["quote"] == ROWS["Full proposal"] and evidence["aligned"] is True and evidence["page"] == 2
    assert study.text(CALL).count("\f") == 1

    manifest = json.loads((study.root / ".biotope/datasets/data/extracted/profile.jsonl.jsonld").read_text())
    assert manifest["biotope:status"] == "processed"
    assert "creator" not in manifest and "license" not in manifest
    assert manifest["prov:wasDerivedFrom"] == [{"@id": "data/pages"}]
    descriptions = {}

    def collect(fields):
        for item in fields:
            descriptions[item["@id"]] = item.get("description")
            collect(item.get("subField", []))

    collect(manifest["recordSet"][0]["field"])
    prefix = "profile.jsonl#profile/values/name/evidence/"
    described = {key.removeprefix(prefix) for key in descriptions if key.startswith(prefix)}
    assert described == set(lind["values"]["name"]["evidence"])
    assert (
        descriptions["profile.jsonl#profile/values/name/value"]
        == "The researcher's full name, without academic titles."
    )
    assert descriptions["profile.jsonl#profile/values/methods/value"] == (
        "Each experimental or computational method the page lists."
    )
    generated = study.run(
        "source", "generate", ".biotope/datasets/data/extracted/profile.jsonl.jsonld", "--out", "graph/sources"
    )
    assert generated.exit_code == 0, generated.output
    schema = next((study.root / "graph/sources").rglob("schema.py")).read_text()
    assert "UnknownValue" not in schema and re.search(r"methods: list\[ProfileJsonlProfileValuesMethods\b", schema)

    texts = [str(path.relative_to(study.root)) for path in (study.root / ".biotope/texts").glob("*.txt")]
    assert len(texts) == 3
    ignored = subprocess.run(["git", "check-ignore", *texts], cwd=study.root, capture_output=True, text=True)
    assert sorted(ignored.stdout.split()) == sorted(texts)
    tracked = [
        "data/extracted/profile.jsonl",
        ".biotope/datasets/data/extracted/profile.jsonl.jsonld",
        ".biotope/datasets/data/pages.jsonld",
        ".biotope/datasets/data/calls.jsonld",
    ]
    assert subprocess.run(["git", "check-ignore", *tracked], cwd=study.root).returncode == 1
    documents = subprocess.run(["git", "check-ignore", LIND, CALL], cwd=study.root, capture_output=True, text=True)
    assert documents.stdout.split() == [LIND, CALL]


def test_run_reuses_stored_records_until_an_input_changes(study, monkeypatch):
    assert study.extract("run", PROFILE, "data/pages")[0].exit_code == 0
    sent = len(study.endpoint.requests)
    before = study.snapshot()
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0 and len(study.endpoint.requests) == sent
    assert statuses(report) == {LIND: "reused", OKAFOR: "reused"} and study.snapshot() == before
    monkeypatch.chdir(study.root / "data")
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0 and report["output"] == "data/extracted/profile.jsonl" and study.snapshot() == before
    monkeypatch.chdir(study.root)
    shutil.rmtree(study.root / ".biotope/texts")
    before = study.snapshot()
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0 and len(study.endpoint.requests) == sent and study.snapshot() == before

    stored = study.records("profile")
    (study.root / "data/extracted/profile.jsonl").unlink()
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"} and len(study.endpoint.requests) == sent + 2
    assert study.records("profile") == stored
    sent = len(study.endpoint.requests)

    page = study.root / OKAFOR
    page.write_text(page.read_text().replace("tissue images", "stained tissue images"))
    result, report = study.extract("run", PROFILE, "data/pages")
    assert statuses(report) == {LIND: "reused", OKAFOR: "extracted"} and len(study.endpoint.requests) == sent + 1

    changes = [
        lambda: study.configure(
            extractor="llm", endpoint=study.endpoint.url, model="test/other", key_env="OPENROUTER_API_KEY"
        ),
        lambda: study.configure(
            extractor="llm",
            endpoint=study.endpoint.url.replace("/v1", "/v2"),
            model="test/other",
            key_env="OPENROUTER_API_KEY",
        ),
        lambda: (study.root / "graph/extraction/schemas.py").write_text(
            (study.root / "graph/extraction/schemas.py").read_text().replace("without academic titles", "as written")
        ),
        lambda: monkeypatch.setattr(llm, "SYSTEM", llm.SYSTEM + " Be brief."),
    ]
    for change in changes:
        change()
        sent = len(study.endpoint.requests)
        result, report = study.extract("run", PROFILE, "data/pages")
        assert result.exit_code == 0, result.output
        assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"}
        assert len(study.endpoint.requests) == sent + 2
    assert study.endpoint.requests[-1]["path"] == "/v2/chat/completions"

    shutil.copy(study.root / LIND, study.root / OKAFOR)
    assert study.extract("run", PROFILE, "data/pages")[0].exit_code == 0
    moved = study.run("mv", "-r", "data/pages", "data/profiles")
    assert moved.exit_code == 0, moved.output
    sent = len(study.endpoint.requests)
    result, report = study.extract("run", PROFILE, "data/profiles")
    assert result.exit_code == 0 and len(study.endpoint.requests) == sent
    assert [record["id"] for record in study.records("profile")] == [
        "data/profiles/lind.html",
        "data/profiles/okafor.html",
    ]
    assert report["moved"] == [
        {"from": LIND, "to": "data/profiles/lind.html"},
        {"from": OKAFOR, "to": "data/profiles/okafor.html"},
    ]
    assert report["appeared"] == [] and report["disappeared"] == []


def test_an_annotated_extracted_dataset_keeps_its_annotation_and_its_schema_descriptions(study):
    assert study.extract("run", PROFILE, "data/pages")[0].exit_code == 0
    given = ("description=Profiles of the researchers.", "url=https://example.org/profiles")
    annotated = study.run("annotate", "set", "data/extracted/profile.jsonl", *given)
    assert annotated.exit_code == 0, annotated.output
    annotation = study.root / "data/extracted/profile.jsonl.biotope.yaml"
    written = annotation.read_bytes()
    name = "profile.jsonl#profile/values/name/value"

    def described():
        data = json.loads((study.root / ".biotope/datasets/data/extracted/profile.jsonl.jsonld").read_text())
        fields = {}

        def collect(items):
            for item in items:
                fields[item["@id"]] = item.get("description")
                collect(item.get("subField", []))

        collect(data["recordSet"][0]["field"])
        return (data["description"], data["url"]), fields[name]

    assert described() == (
        ("Profiles of the researchers.", "https://example.org/profiles"),
        "The researcher's full name, without academic titles.",
    )
    schema = study.root / "graph/extraction/schemas.py"
    schema.write_text(schema.read_text().replace("without academic titles", "as written"))
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"}
    assert annotation.read_bytes() == written
    assert described() == (
        ("Profiles of the researchers.", "https://example.org/profiles"),
        "The researcher's full name, as written.",
    )


def test_record_ids_follow_the_record_key(study):
    assert study.extract("run", ROUND, "data/calls")[0].exit_code == 0
    first = study.records("funding_round")
    assert [record["id"] for record in first] == [
        'data/calls/call.pdf#round="Full proposal"',
        'data/calls/call.pdf#round="Pre-proposal"',
        'data/calls/call.pdf#round="Renewal"',
    ]

    reordered = {"records": ROUNDS["records"][::-1]}
    study.endpoint.reply("Funding rounds", reordered)
    study.configure(extractor="llm", endpoint=study.endpoint.url, model="test/other", key_env="OPENROUTER_API_KEY")
    result, report = study.extract("run", ROUND, "data/calls")
    assert statuses(report) == {CALL: "extracted"}
    assert [record["id"] for record in study.records("funding_round")] == [record["id"] for record in first]
    assert report["appeared"] == [] and report["disappeared"] == []

    renamed = {
        "records": [*ROUNDS["records"][:2], funding_round("Extension", "1 March 2029", "750 000 EUR", ROWS["Renewal"])]
    }
    study.endpoint.reply("Funding rounds", renamed)
    study.configure(extractor="llm", endpoint=study.endpoint.url, model="test/third", key_env="OPENROUTER_API_KEY")
    result, report = study.extract("run", ROUND, "data/calls")
    assert result.exit_code == 0, result.output
    assert report["disappeared"] == ['data/calls/call.pdf#round="Renewal"']
    assert report["appeared"] == ['data/calls/call.pdf#round="Extension"']

    for duplicate in (ROUNDS["records"][1], funding_round(None, "1 May 2027", None, ROWS["Full proposal"])):
        study.endpoint.reply("Funding rounds", {"records": [*ROUNDS["records"], duplicate, duplicate]})
        study.configure(
            extractor="llm",
            endpoint=study.endpoint.url,
            model=f"test/{len(study.endpoint.requests)}",
            key_env="OPENROUTER_API_KEY",
        )
        result, report = study.extract("run", ROUND, "data/calls")
        assert result.exit_code != 0
        [document] = report["documents"]
        assert document["status"] == "failed" and "round" in document["reason"]

    (study.root / "graph/extraction/readings.py").write_text(
        "from dataclasses import dataclass\nfrom typing import ClassVar\n\n\n@dataclass(frozen=True)\n"
        "class Reading:\n    __record_key__: ClassVar[tuple[str, ...]] = ('number',)\n\n    number: float\n"
    )
    (study.root / "data/readings.txt").write_text("Readings: 1 and 1.0\n")
    ids = []
    for numbers in ([1], [1.0], [1, 1.0]):
        records = [{"number": quoted(number, "1")} for number in numbers]
        study.endpoint.reply("Readings", {"records": records})
        result, report = study.extract("try", "graph/extraction/readings.py:Reading", "data/readings.txt")
        [document] = report["documents"]
        ids.append([record["id"] for record in document["records"]])
    assert ids[0] == ids[1] == ["data/readings.txt#number=1.0"]
    assert result.exit_code != 0 and document["status"] == "failed" and "number" in document["reason"]


def test_failed_missing_and_removed_documents(study, monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    study.endpoint.reply("Chidi Okafor", 400)
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code != 0
    assert statuses(report) == {LIND: "extracted", OKAFOR: "failed"}
    assert "400" in report["documents"][1]["reason"]
    assert [record["id"] for record in study.records("profile")] == [LIND]

    (study.root / OKAFOR).unlink()
    rebaked = study.run("add", "data/pages", "--rebake")
    assert rebaked.exit_code == 0, rebaked.output
    manifest = study.root / ".biotope/datasets/data/pages.jsonld"
    metadata = json.loads(manifest.read_text())
    for entry in metadata["distribution"]:
        if entry.get("contentUrl") == LIND:
            entry["contentUrl"] = "lind.html"
    manifest.write_text(json.dumps(metadata, indent=2))
    (study.root / LIND).unlink()
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code != 0
    assert statuses(report) == {LIND: "missing"} and report["disappeared"] == []
    assert [record["id"] for record in study.records("profile")] == [LIND]

    shutil.copy(FIXTURES / "lind.html", study.root / LIND)
    shutil.copy(FIXTURES / "okafor.html", study.root / OKAFOR)
    assert study.run("add", "data/pages", "--rebake").exit_code == 0
    study.endpoint.reply("Chidi Okafor", {"record": None})
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0 and statuses(report) == {LIND: "reused", OKAFOR: "empty"}
    (study.root / LIND).unlink()
    rebaked = study.run("add", "data/pages", "--rebake")
    assert rebaked.exit_code == 0, rebaked.output
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert report["disappeared"] == [LIND] and statuses(report) == {OKAFOR: "reused"}
    assert study.records("profile") == []


def test_a_rerun_registers_records_an_interrupted_run_stored(study, monkeypatch):
    assert study.extract("run", PROFILE, "data/pages")[0].exit_code == 0
    study.endpoint.reply("Mara Lind", {"record": {**LIND_ANSWER["record"], "group": quoted(None)}})
    study.configure(extractor="llm", endpoint=study.endpoint.url, model="test/other", key_env="OPENROUTER_API_KEY")
    replace = os.replace

    def interrupted(source, target):
        if str(target).endswith("profile.jsonl.jsonld"):
            raise OSError("interrupted")
        replace(source, target)

    monkeypatch.setattr(os, "replace", interrupted)
    assert study.run("extract", "run", PROFILE, "data/pages").exit_code != 0
    monkeypatch.setattr(os, "replace", replace)
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    manifest = json.loads((study.root / ".biotope/datasets/data/extracted/profile.jsonl.jsonld").read_text())
    [stored] = [
        entry for entry in manifest["distribution"] if entry.get("contentUrl") == "data/extracted/profile.jsonl"
    ]
    assert stored["sha256"] == hashlib.sha256((study.root / "data/extracted/profile.jsonl").read_bytes()).hexdigest()


def test_a_project_extractor_runs_by_configuration(study):
    (study.root / "graph/extraction/rules.py").write_text(
        (FIXTURES / "rules.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    study.configure(extractor="graph/extraction/rules.py:LineExtractor", version="1", line=1)
    tried = study.run("extract", "try", PROFILE, LIND)
    assert tried.exit_code == 0, tried.output
    assert "Mara Lind" in tried.output and "line 1" in tried.output

    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    lind = study.records("profile")[0]
    assert lind["values"]["name"]["value"] == "Dr. Mara Lind"
    assert lind["values"]["name"]["evidence"]["locator"] == "line 1"
    assert lind["provenance"]["extractor"] == {"name": "lines", "version": "1", "settings": {"line": 1}}

    study.configure(extractor="graph/extraction/rules.py:LineExtractor", version="2", line=1)
    result, report = study.extract("run", PROFILE, "data/pages")
    assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"}
    assert study.endpoint.requests == []

    study.configure(extractor="graph/extraction/rules.py:LineExtractor", version="3", line=0)
    tried = study.extract("try", PROFILE, LIND)[1]["documents"][0]
    ran = study.extract("run", PROFILE, "data/pages")[1]["documents"][0]
    assert tried["status"] == ran["status"] == "failed"
    assert tried["reason"] == ran["reason"] == "ValueError: line numbers start at 1"


def decoded(annotation, value):
    if value is None:
        return None
    if get_origin(annotation) in (Union, types.UnionType):
        [annotation] = [member for member in get_args(annotation) if member is not type(None)]
    if get_origin(annotation) is list:
        return [decoded(get_args(annotation)[0], item) for item in value]
    if is_dataclass(annotation):
        hints = get_type_hints(annotation)
        return annotation(**{item.name: decoded(hints[item.name], value.get(item.name)) for item in fields(annotation)})
    return float(value) if annotation is float else value


FIRST_LINE = "graph/extraction/rules.py:FirstLineExtractor"


@pytest.mark.parametrize(
    "runs,described",
    [
        ([{}], {"endpoint": "sc:Text", "model": "sc:Text"}),
        ([{"extractor": FIRST_LINE, "recorded": {}}], None),
        (
            [{"extractor": FIRST_LINE, "recorded": {"line": 1, "pages": [1, 2], "options": {"strict": True}}}],
            {"line": "sc:Integer"},
        ),
        (
            [
                {
                    "extractor": FIRST_LINE,
                    "recorded": {"line": 1, "pages": 1, "threshold": 0, "mode": None, "unit": "mm"},
                },
                {
                    "extractor": FIRST_LINE,
                    "recorded": {"line": 1, "pages": [1, 2], "threshold": 0.5, "mode": 3, "unit": 2},
                    "fail": "lind",
                },
            ],
            {"line": "sc:Integer", "threshold": "sc:Float", "mode": "sc:Integer"},
        ),
    ],
    ids=["llm", "no settings", "structured settings", "settings changed shape"],
)
def test_generated_sources_load_extracted_records(study, monkeypatch, runs, described):
    for extractor in runs:
        if extractor:
            shutil.copy(FIXTURES / "rules.py", study.root / "graph/extraction/rules.py")
            study.configure(**extractor)
        result, _ = study.extract("run", PROFILE, "data/pages")
        assert (result.exit_code == 0) != ("fail" in extractor), result.output
    manifest = json.loads((study.root / ".biotope/datasets/data/extracted/profile.jsonl.jsonld").read_text())
    [provenance] = [item for item in manifest["recordSet"][0]["field"] if item["name"] == "provenance"]
    [extractor_field] = [item for item in provenance["subField"] if item["name"] == "extractor"]
    settings = [item for item in extractor_field["subField"] if item["name"] == "settings"]
    assert ({item["name"]: item["dataType"] for item in settings[0]["subField"]} if settings else None) == described
    generated = study.run(
        "source", "generate", ".biotope/datasets/data/extracted/profile.jsonl.jsonld", "--out", "graph/sources"
    )
    assert generated.exit_code == 0, generated.output

    monkeypatch.syspath_prepend(str(study.root))
    package = next((study.root / "graph/sources").rglob("schema.py")).parent.relative_to(study.root)
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


def test_missing_configuration_stops_before_any_request_and_the_key_stays_secret(study, monkeypatch):
    study.configure(extractor="llm", endpoint=study.endpoint.url, key_env="OPENROUTER_API_KEY")
    for command in (["try", PROFILE, LIND], ["run", PROFILE, "data/pages"]):
        result = study.run("extract", *command)
        assert result.exit_code != 0 and "extraction.model" in result.output
    study.configure(extractor="llm", endpoint=study.endpoint.url, model="test/model", key_env="OPENROUTER_API_KEY")
    monkeypatch.delenv("OPENROUTER_API_KEY")
    for command in (["try", PROFILE, LIND], ["run", PROFILE, "data/pages"]):
        result = study.run("extract", *command)
        assert result.exit_code != 0 and "OPENROUTER_API_KEY" in result.output
    assert study.endpoint.requests == []

    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    outputs = [study.run("extract", "try", PROFILE, LIND), study.run("extract", "run", PROFILE, "data/pages")]
    outputs.append(study.run("extract", "run", PROFILE, "data/pages", "--json"))
    assert all(result.exit_code == 0 for result in outputs)
    assert {request["authorization"] for request in study.endpoint.requests} == {f"Bearer {KEY}"}
    assert not any(KEY in result.output for result in outputs)
    assert not any(KEY.encode() in content for content in study.snapshot().values())
    assert not any(KEY.encode() in path.read_bytes() for path in (study.root / ".git").rglob("*") if path.is_file())


def test_try_shows_records_and_changes_nothing(study):
    before = study.snapshot()
    result = study.run("extract", "try", PROFILE, LIND, OKAFOR)
    assert result.exit_code == 0, result.output
    for shown in ("Mara Lind", '"Dr. Mara Lind"', "single-cell RNA sequencing", "Machine Learning for Tissues Lab"):
        assert shown in result.output
    assert "unaligned" in result.output
    rounds, report = study.extract("try", ROUND, CALL)
    assert rounds.exit_code == 0 and f"Extracting 1/1 {CALL}" in rounds.stderr
    [document] = report["documents"]
    assert {record["id"] for record in document["records"]} >= {'data/calls/call.pdf#round="Renewal"'}
    assert study.snapshot() == before


def test_schema_revision_and_refused_constructs(study, tmp_path):
    source = (FIXTURES / "schemas.py").read_text()

    def schema(text, name="Profile"):
        path = tmp_path / f"schema_{abs(hash(text))}.py"
        path.write_text(text)
        return Schema.load(f"{path}:{name}")

    revision = schema(source).revision
    assert schema(source).revision == revision == Schema.load(f"{FIXTURES / 'schemas.py'}:Profile").revision
    described = source.replace("without academic titles", "as the page writes it")
    added = source.replace(
        "    methods: list[str]",
        '    email: str | None = field(metadata={"description": "Email."})\n    methods: list[str]',
    )
    assert len({revision, schema(described).revision, schema(added).revision}) == 3

    refused = {
        "links": "dict[str, str]",
        "span": "tuple[int, int]",
        "anything": "Any",
        "tags": "set[str]",
        "maybe": "list[str] | None",
        "either": "int | str",
        "nested": "Profile",
    }
    for name, annotation in refused.items():
        text = source.replace("from typing import ClassVar", "from typing import Any, ClassVar").replace(
            "class FundingRound:", f"class FundingRound:\n    {name}: {annotation}"
        )
        with pytest.raises(ValueError, match=name):
            schema(text, "FundingRound")
    bad_key = source.replace('("round",)', '("missing",)')
    with pytest.raises(ValueError, match="missing"):
        schema(bad_key, "FundingRound")

    shown = study.run("extract", "schema", ROUND)
    assert shown.exit_code == 0, shown.output
    described = json.loads(shown.output)
    assert (described["name"], described["key"]) == ("FundingRound", ["round"])
    assert described["revision"] == study.extract("try", ROUND, CALL)[1]["schema"]["revision"]
    deadline = described["json_schema"]["properties"]["records"]["items"]["properties"]["deadline"]
    assert deadline["description"] == "The round's submission deadline, as written."
    single = json.loads(study.run("extract", "schema", PROFILE).output)["json_schema"]["properties"]
    assert list(single) == ["record"]
    record, nothing = single["record"]["anyOf"]
    assert list(record["properties"]) == ["name", "group", "methods"] and nothing == {"type": "null"}
    requests = len(study.endpoint.requests)

    (study.root / "graph/extraction/schemas.py").write_text(
        source.replace("    methods: list[str]", "    links: dict[str, str]")
    )
    for command in (["try", PROFILE, LIND], ["schema", PROFILE]):
        result = study.run("extract", *command)
        assert result.exit_code != 0 and "links" in result.output
    assert len(study.endpoint.requests) == requests


def test_empty_or_invalid_answers_are_retried(study, monkeypatch):
    waits = []
    monkeypatch.setattr(llm.time, "sleep", waits.append)
    study.endpoint.reply("Mara Lind", None, times=1)
    study.endpoint.reply("Mara Lind", '{"record": {"name"', times=1)
    study.endpoint.reply("Chidi Okafor", "")
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code != 0
    assert statuses(report) == {LIND: "extracted", OKAFOR: "failed"}
    assert "empty" in report["documents"][1]["reason"]
    asked = [request["body"]["messages"][-1]["content"] for request in study.endpoint.requests]
    assert sum("Mara Lind" in text for text in asked) == 3
    assert sum("Chidi Okafor" in text for text in asked) == llm.ATTEMPTS
    assert sorted(waits) == [2, 2, 4, 4, 8]
    assert [record["id"] for record in study.records("profile")] == [LIND]


def test_a_null_record_is_retried_and_reported_as_empty(study, monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    study.endpoint.reply("Mara Lind", {"record": None}, times=1)
    study.endpoint.reply("Chidi Okafor", {"record": None})
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert statuses(report) == {LIND: "extracted", OKAFOR: "empty"}
    asked = [request["body"]["messages"][-1]["content"] for request in study.endpoint.requests]
    assert sum("Mara Lind" in text for text in asked) == 2
    assert sum("Chidi Okafor" in text for text in asked) == llm.ATTEMPTS
    assert [record["id"] for record in study.records("profile")] == [LIND]
    shown = study.run("extract", "run", PROFILE, "data/pages", "--redo", OKAFOR)
    assert shown.exit_code == 0 and "empty, 0 records" in " ".join(shown.output.split())
    tried, report = study.extract("try", PROFILE, OKAFOR, LIND)
    assert tried.exit_code == 0 and statuses(report) == {OKAFOR: "empty", LIND: "extracted"}

    study.endpoint.reply("Mara Lind", 503)
    study.endpoint.reply("Mara Lind", {"record": None}, times=1)
    result, report = study.extract("run", PROFILE, "data/pages", "--redo", LIND)
    assert result.exit_code != 0 and statuses(report)[LIND] == "failed" and "503" in report["documents"][0]["reason"]
    assert [record["id"] for record in study.records("profile")] == [LIND]


def test_parallel_extraction_changes_neither_output_nor_report(study):
    study.endpoint.delay = 0.3
    outcomes = []
    for parallel in (1, 2):
        study.configure(
            extractor="llm",
            endpoint=study.endpoint.url,
            model="test/model",
            key_env="OPENROUTER_API_KEY",
            parallel=parallel,
        )
        for stored in ("data/extracted", ".biotope/extraction", ".biotope/datasets/data/extracted", "../cache"):
            shutil.rmtree(study.root / stored, ignore_errors=True)
        study.endpoint.most_busy = 0
        result, report = study.extract("run", PROFILE, "data/pages")
        assert result.exit_code == 0, result.output
        tried, attempt = study.extract("try", PROFILE, LIND, OKAFOR)
        assert tried.exit_code == 0, tried.output
        assert study.endpoint.most_busy == parallel
        outcomes.append((study.records("profile"), report, result.stderr, attempt, tried.stderr))
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][2].index(f"Extracting 1/2 {LIND}") < outcomes[0][2].index(f"Extracting 2/2 {OKAFOR}")
    sent = len(study.endpoint.requests)
    study.configure(
        extractor="llm", endpoint=study.endpoint.url, model="test/model", key_env="OPENROUTER_API_KEY", parallel=3
    )
    result, report = study.extract("run", PROFILE, "data/pages")
    assert statuses(report) == {LIND: "reused", OKAFOR: "reused"} and len(study.endpoint.requests) == sent
    study.configure(
        extractor="llm", endpoint=study.endpoint.url, model="test/model", key_env="OPENROUTER_API_KEY", parallel=0
    )
    result = study.run("extract", "run", PROFILE, "data/pages")
    assert result.exit_code != 0 and "extraction.parallel" in result.output


def test_redo_extracts_chosen_documents_again(study):
    assert study.extract("run", PROFILE, "data/pages")[0].exit_code == 0
    sent = len(study.endpoint.requests)
    study.endpoint.reply("Mara Lind", {"record": {**LIND_ANSWER["record"], "group": quoted(None)}})
    result, report = study.extract("run", PROFILE, "data/pages", "--redo", LIND)
    assert result.exit_code == 0, result.output
    assert statuses(report) == {LIND: "extracted", OKAFOR: "reused"} and len(study.endpoint.requests) == sent + 1
    lind, okafor = study.records("profile")
    assert lind["values"]["group"]["value"] is None and lind["provenance"]["redone"] is True
    assert "redone" not in okafor["provenance"]

    before = study.snapshot()
    result, report = study.extract("run", PROFILE, "data/pages")
    assert statuses(report) == {LIND: "reused", OKAFOR: "reused"} and len(study.endpoint.requests) == sent + 1
    assert study.snapshot() == before

    result, report = study.extract("run", PROFILE, "data/pages", "--redo", CALL)
    assert result.exit_code != 0 and CALL in report["error"]
    assert len(study.endpoint.requests) == sent + 1 and study.snapshot() == before


def test_short_and_repeated_quotes_are_weak_evidence(study):
    study.endpoint.reply(
        "Mara Lind",
        {
            "record": {
                "name": quoted("Mara Lind", "Dr. Mara Lind"),
                "group": quoted("Spatial Atlas Group"),
                "methods": [quoted("lung imaging", "lung"), quoted("Uppsala"), quoted("tissue imaging")],
            }
        },
    )
    result, report = study.extract("try", PROFILE, LIND)
    assert result.exit_code == 0, result.output
    [record] = report["documents"][0]["records"]
    lung, uppsala, imaging = (item["evidence"] for item in record["values"]["methods"])
    assert (lung["aligned"], lung["weak"], lung["occurrences"]) == (True, ["short", "repeated"], 2)
    assert (uppsala["weak"], uppsala["occurrences"]) == (["short"], 1)
    assert (imaging["aligned"], imaging["weak"], imaging["occurrences"]) == (False, None, 0)
    assert record["values"]["name"]["evidence"]["weak"] == []
    assert report["weak"] == [
        {"record": LIND, "field": "methods", "quote": "lung", "reasons": ["short", "repeated"]},
        {"record": LIND, "field": "methods", "quote": "Uppsala", "reasons": ["short"]},
    ]
    assert report["unaligned"] == [{"record": LIND, "field": "methods", "quote": "tissue imaging"}]
    assert report["counts"] == {"values": 5, "aligned": 4, "unaligned": 1, "weak": 2}
    shown = study.run("extract", "try", PROFILE, LIND)
    assert re.search(r'"lung" \(characters \d+-\d+; weak: short, found 2 times\)', shown.output)

    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert [item["quote"] for item in report["weak"]] == ["lung", "Uppsala", "Chidi Okafor", "graph neural networks"]
    assert report["counts"]["weak"] == 4 and len(report["unaligned"]) == 2

    sentence = "The atlas covers adult human lung tissue."
    (study.root / "data/notes.txt").write_text(f"{sentence}\nAtlas notes\n{sentence}\n")
    study.endpoint.reply(
        "Atlas notes",
        {"record": {"name": quoted("Atlas notes"), "group": quoted(None), "methods": [quoted(sentence)]}},
    )
    result, report = study.extract("try", PROFILE, "data/notes.txt")
    [record] = report["documents"][0]["records"]
    [evidence] = [item["evidence"] for item in record["values"]["methods"]]
    assert (evidence["occurrences"], evidence["weak"]) == (2, []) and report["weak"] == []


def test_quotes_found_only_in_running_heads_do_not_support_a_record(study):
    (study.root / "data/reports").mkdir()
    shutil.copy(FIXTURES / "report.pdf", study.root / REPORT)
    assert study.run("add", "data/reports").exit_code == 0
    study.endpoint.reply(
        "Ines Navarro",
        {
            "record": {
                "name": quoted("Annual Report", "ANNUAL REPORT 2026"),
                "group": quoted("Spatial Atlas Group"),
                "methods": [
                    quoted("reporting", "ANNUAL REPORT 2026 | Spatial Atlas Group"),
                    quoted("pagination", "Page 2 of 3"),
                ],
            }
        },
    )
    result, report = study.extract("run", PROFILE, "data/reports")
    assert result.exit_code == 0, result.output
    assert statuses(report) == {REPORT: "unsupported"}
    assert report["unsupported"] == [{"record": REPORT, "values": 4, "unaligned": 0, "running_head": 3}]
    [record] = study.records("profile")
    name, group = (record["values"][field]["evidence"] for field in ("name", "group"))
    assert (record["supported"], name["aligned"], name["weak"]) == (False, True, ["repeated", "running head"])
    assert (group["aligned"], group["weak"], group["occurrences"]) == (True, ["repeated"], 5)
    assert {
        "record": REPORT,
        "field": "name",
        "quote": "ANNUAL REPORT 2026",
        "reasons": ["repeated", "running head"],
    } in report["weak"]
    shown = " ".join(study.run("extract", "try", PROFILE, REPORT).output.split())
    assert re.search(r'"Page 2 of 3" \(page 2, characters \d+-\d+; weak: short, running head\)', shown)
    assert "unsupported: 0 of 4 values have no aligned evidence, 3 are found only in running heads" in shown

    study.endpoint.reply(
        "Ines Navarro",
        {
            "record": {
                "name": quoted("Ines Navarro", "Dr. Ines Navarro"),
                "group": quoted("Spatial Atlas Group"),
                "methods": [quoted("spatial transcriptomics")],
            }
        },
    )
    result, report = study.extract("run", PROFILE, "data/reports", "--redo", REPORT)
    assert result.exit_code == 0 and statuses(report) == {REPORT: "extracted"} and report["unsupported"] == []


def test_an_interrupted_run_changes_the_output_only_when_a_later_run_completes(study):
    study.configure(
        extractor="llm", endpoint=study.endpoint.url, model="test/model", key_env="OPENROUTER_API_KEY", parallel=1
    )
    (study.root / SUMMARY).write_text("Bridge call\nBridge 1 June 2027\n")
    assert study.run("add", "data/calls", "--rebake").exit_code == 0
    study.endpoint.reply(
        "Bridge call", {"records": [funding_round("Bridge", "1 June 2027", None, "Bridge 1 June 2027")]}
    )
    assert study.extract("run", ROUND, "data/calls")[0].exit_code == 0
    stored = ("data/extracted/funding_round.jsonl", ".biotope/extraction/data/extracted/funding_round.json")
    committed = [(study.root / path).read_bytes() for path in stored]

    def untracked():
        listed = ["git", "ls-files", "--others", "--exclude-standard"]
        return subprocess.run(listed, cwd=study.root, capture_output=True, text=True).stdout

    clean = untracked()
    renamed = [*ROUNDS["records"][:2], funding_round("Extension", "1 March 2029", "750 000 EUR", ROWS["Renewal"])]
    study.endpoint.reply("Open Atlas Fellowship", {"records": renamed})
    study.configure(
        extractor="llm", endpoint=study.endpoint.url, model="test/other", key_env="OPENROUTER_API_KEY", parallel=1
    )
    released = study.endpoint.hold("Bridge call")
    sent = len(study.endpoint.requests)
    process = subprocess.Popen(
        [sys.executable, "-c", "from biotope.cli import cli; cli()", "extract", "run", ROUND, "data/calls"],
        cwd=study.root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 60
    while len(study.endpoint.requests) < sent + 2 and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    process.kill()
    process.wait()
    released.set()
    assert len(study.endpoint.requests) == sent + 2
    assert [(study.root / path).read_bytes() for path in stored] == committed and untracked() == clean

    result, report = study.extract("run", ROUND, "data/calls")
    assert result.exit_code == 0, result.output
    assert statuses(report) == {CALL: "reused", SUMMARY: "extracted"} and len(study.endpoint.requests) == sent + 3
    assert report["disappeared"] == ['data/calls/call.pdf#round="Renewal"']
    assert report["appeared"] == ['data/calls/call.pdf#round="Extension"']
    assert 'data/calls/call.pdf#round="Extension"' in {record["id"] for record in study.records("funding_round")}
    assert untracked() == clean


def test_documents_keep_their_records_when_they_cannot_be_read_or_lost_their_run_state(study, monkeypatch):
    replace = os.replace

    def interrupted(source, target):
        if str(target).endswith("profile.json"):
            raise OSError("interrupted")
        replace(source, target)

    monkeypatch.setattr(os, "replace", interrupted)
    assert study.run("extract", "run", PROFILE, "data/pages").exit_code != 0
    monkeypatch.setattr(os, "replace", replace)
    assert [record["id"] for record in study.records("profile")] == [LIND, OKAFOR]
    page = (study.root / LIND).read_bytes()
    (study.root / LIND).unlink()
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code != 0 and statuses(report)[LIND] == "missing" and report["documents"][0]["records"] == 1
    assert report["disappeared"] == [] and [record["id"] for record in study.records("profile")] == [LIND, OKAFOR]

    (study.root / LIND).write_bytes(page)
    (study.root / ".biotope/extraction/data/extracted/profile.json").unlink()
    study.endpoint.reply("Mara Lind", 400)
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code != 0 and statuses(report)[LIND] == "failed" and report["documents"][0]["records"] == 1
    assert report["disappeared"] == [] and [record["id"] for record in study.records("profile")] == [LIND, OKAFOR]

    study.endpoint.reply("Mara Lind", LIND_ANSWER)
    study.configure(extractor="llm", endpoint=study.endpoint.url, model="test/other", key_env="OPENROUTER_API_KEY")
    (study.root / OKAFOR).chmod(0)
    try:
        result, report = study.extract("run", PROFILE, "data/pages")
    finally:
        (study.root / OKAFOR).chmod(0o644)
    assert result.exit_code != 0
    assert statuses(report) == {LIND: "extracted", OKAFOR: "failed"}
    assert "PermissionError" in report["documents"][1]["reason"] and report["documents"][1]["records"] == 1
    assert report["disappeared"] == [] and [record["id"] for record in study.records("profile")] == [LIND, OKAFOR]


def test_a_conversion_change_aligns_reused_quotes_again(study, monkeypatch):
    assert study.extract("run", PROFILE, "data/pages")[0].exit_code == 0
    sent = len(study.endpoint.requests)
    monkeypatch.setattr(converter, "HIDDEN_TAGS", converter.HIDDEN_TAGS - {"nav"})
    monkeypatch.setattr(converter, "CONVERSION", converter.CONVERSION + 1)
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert statuses(report) == {LIND: "reused", OKAFOR: "reused"} and len(study.endpoint.requests) == sent
    shutil.rmtree(study.root / ".biotope/texts")
    checked = 0
    for record in study.records("profile"):
        assert record["provenance"]["conversion"] == converter.CONVERSION
        shown = study.run("extract", "text", record["document"]).output
        values = record["values"]
        for value in [values["name"], values["group"], *values["methods"]]:
            evidence = value["evidence"]
            if evidence and evidence["aligned"]:
                assert squeeze(shown[evidence["start"] : evidence["end"]]) == squeeze(evidence["quote"])
                checked += 1
    assert checked == 6
    before = study.snapshot()
    result, report = study.extract("run", PROFILE, "data/pages")
    assert statuses(report) == {LIND: "reused", OKAFOR: "reused"} and study.snapshot() == before


def test_quotes_align_where_case_folding_lengthens_the_text(study):
    (study.root / "data/notes.txt").write_text("\u0130stanbul\nMara Lind\nSpatial Atlas Group\n")
    study.endpoint.reply(
        "\u0130stanbul",
        {
            "record": {
                "name": quoted("Mara Lind", "mara lind"),
                "group": quoted("Spatial Atlas Group", "spatial atlas group"),
                "methods": [],
            }
        },
    )
    result, report = study.extract("try", PROFILE, "data/notes.txt")
    assert result.exit_code == 0, result.output
    [record] = report["documents"][0]["records"]
    shown = study.run("extract", "text", "data/notes.txt").output
    for name, expected in (("name", "Mara Lind"), ("group", "Spatial Atlas Group")):
        evidence = record["values"][name]["evidence"]
        assert evidence["aligned"] and shown[evidence["start"] : evidence["end"]] == expected


def test_text_shows_what_the_extractor_reads(study):
    page = study.run("extract", "text", LIND)
    assert page.exit_code == 0, page.output
    assert "Dr. Mara Lind" in page.output and "Research" in page.output
    for chrome in ("Open Atlases Portal", "Home", "Contact", "Spatial Biology", "2026 Institute"):
        assert chrome not in page.output
    assert study.extract("run", PROFILE, "data/pages")[0].exit_code == 0
    asked = [request["body"]["messages"][-1]["content"] for request in study.endpoint.requests]
    [sent] = [text for text in asked if "Mara Lind" in text]
    assert sent.endswith(page.output) and "Home" not in sent
    assert study.extract("run", ROUND, "data/calls")[0].exit_code == 0
    before = study.snapshot()
    shown = study.run("extract", "text", CALL)
    assert shown.exit_code == 0, shown.output
    assert shown.output.count("\f") == 1 and study.snapshot() == before
    for record in study.records("funding_round"):
        evidence = record["values"]["deadline"]["evidence"]
        assert shown.output[evidence["start"] : evidence["end"]] == evidence["quote"]


def test_run_warns_when_git_ignores_its_output(study):
    with (study.root / ".gitignore").open("a") as ignore:
        ignore.write("\nextracted/\n")
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert report["ignored"] == [
        ".biotope/datasets/data/extracted/profile.jsonl.jsonld",
        ".biotope/extraction/data/extracted/profile.json",
        "data/extracted/profile.jsonl",
    ]
    shown = study.run("extract", "run", PROFILE, "data/pages")
    assert "git ignores data/extracted/profile.jsonl" in " ".join(shown.output.split())


def test_schemas_live_in_the_graph_and_records_in_data(study):
    shutil.copy(FIXTURES / "schemas.py", study.root / "graph/extraction/profile.py")
    schema = "graph/extraction/profile.py:Profile"
    result, report = study.extract("run", schema, "data/pages")
    assert result.exit_code == 0 and report["output"] == "data/extracted/profile.jsonl", result.output
    assert (study.root / "data/extracted/profile.jsonl").is_file()
    result, report = study.extract("run", schema, "data/pages", "--out", "data/people.jsonl")
    assert result.exit_code == 0 and report["output"] == "data/people.jsonl", result.output
    assert (study.root / "data/people.jsonl").is_file()

    pipeline = study.root / "graph/pipelines/build_graph.py"
    pipeline.write_text(pipeline.read_text().replace('name="",', 'name="pages",').replace('scope="",', 'scope="none",'))
    compose = study.root / "graph/pipelines/compose.py"
    compose.write_text(
        compose.read_text().replace("    raise NotImplementedError(", "    return\n    raise NotImplementedError(")
    )
    built = study.run("graph", "build")
    assert built.exit_code == 0, built.output
    run = json.loads((study.root / "graph/build/run.json").read_text())
    assert str((study.root / "graph/extraction/profile.py").resolve()) in run["definitions"]["code_digests"]
    module = study.root / "graph/extraction/profile.py"
    module.write_text(module.read_text() + '\nWRONG: int = "text"\n')
    checked = study.run("graph", "check", "--json")
    assert checked.exit_code != 0
    assert any(
        finding["code"].startswith("python.") and finding["location"]["path"].endswith("graph/extraction/profile.py")
        for finding in json.loads(checked.output)["findings"]
    )

    moved = study.run("mv", "data/extracted/profile.jsonl", "data/extracted/people.jsonl")
    assert moved.exit_code == 0, moved.output
    assert (study.root / ".biotope/extraction/data/extracted/people.json").is_file()
    sent = len(study.endpoint.requests)
    result, report = study.extract("run", schema, "data/pages", "--out", "data/extracted/people.jsonl")
    assert result.exit_code == 0, result.output
    assert statuses(report) == {LIND: "reused", OKAFOR: "reused"} and len(study.endpoint.requests) == sent


def test_a_record_mostly_without_aligned_evidence_is_kept_for_review(study):
    study.endpoint.reply(
        "Mara Lind",
        {
            "record": {
                "name": quoted("Mara Lind"),
                "group": quoted("Cancer Imaging Group"),
                "methods": [quoted("image analysis"), {"value": "deep learning"}],
            }
        },
    )
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert statuses(report) == {LIND: "unsupported", OKAFOR: "extracted"}
    assert "1 of 1 records" in report["documents"][0]["reason"]
    assert report["unsupported"] == [{"record": LIND, "values": 4, "unaligned": 3, "running_head": 0}]
    lind, okafor = study.records("profile")
    assert (lind["supported"], okafor["supported"]) == (False, True)
    assert lind["values"]["group"]["value"] == "Cancer Imaging Group"
    manifest = json.loads((study.root / ".biotope/datasets/data/extracted/profile.jsonl.jsonld").read_text())
    assert "profile.jsonl#profile/supported" in {item["@id"] for item in manifest["recordSet"][0]["field"]}

    shown = " ".join(study.run("extract", "run", PROFILE, "data/pages").output.split())
    assert "Review data/pages/lind.html unsupported: 3 of 4 values have no aligned evidence" in shown
    tried, report = study.extract("try", PROFILE, LIND)
    assert tried.exit_code == 0 and statuses(report) == {LIND: "unsupported"}
    assert report["unsupported"] == [{"record": LIND, "values": 4, "unaligned": 3, "running_head": 0}]


def test_run_warns_when_the_schema_revision_was_never_tried(study, monkeypatch):
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    [warning] = report["warnings"]
    assert report["schema"]["revision"][:12] in warning and "biotope extract try" in warning
    shown = " ".join(study.run("extract", "run", PROFILE, "data/pages").output.split())
    assert "WARN untried schema" in shown and "never shown with biotope extract try" in shown

    assert study.extract("try", PROFILE, LIND)[0].exit_code == 0
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0 and report["warnings"] == []
    checkout = study.root.parent / "checkout"
    shutil.copytree(study.root, checkout)
    monkeypatch.chdir(checkout)
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0 and report["warnings"] == []
    monkeypatch.chdir(study.root)

    schemas = study.root / "graph/extraction/schemas.py"
    schemas.write_text(schemas.read_text().replace("without academic titles", "as the page writes it"))
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0 and len(report["warnings"]) == 1


@pytest.mark.live
def test_live_extraction_aligns_values(study, monkeypatch):
    if LIVE_KEY:
        monkeypatch.setenv("OPENROUTER_API_KEY", LIVE_KEY)
    else:
        monkeypatch.delenv("OPENROUTER_API_KEY")
    study.configure(
        extractor="llm",
        endpoint="https://openrouter.ai/api/v1",
        model="deepseek/deepseek-v4.1-flash",
        key_env="OPENROUTER_API_KEY",
    )
    values = []
    for schema, dataset in ((PROFILE, "data/pages"), (ROUND, "data/calls")):
        result, report = study.extract("run", schema, dataset)
        assert result.exit_code == 0, result.output
        assert set(statuses(report).values()) == {"extracted"}
    for name in ("profile", "funding_round"):
        for record in study.records(name):
            for value in record["values"].values():
                values += [
                    item for item in (value if isinstance(value, list) else [value]) if item["value"] is not None
                ]
    aligned = sum(bool(item["evidence"] and item["evidence"]["aligned"]) for item in values)
    print(f"aligned {aligned} of {len(values)} non-null values ({aligned / len(values):.0%})")
    assert aligned >= 0.9 * len(values)
    full = next(
        record
        for record in study.records("funding_round")
        if "Full proposal" in str(record["values"]["round"]["value"])
    )
    evidence = full["values"]["deadline"]["evidence"]
    assert evidence["page"] == 2 and squeeze(ROWS["Full proposal"]) in squeeze(evidence["quote"])


def test_the_records_file_takes_the_schema_name_as_the_topology_layout_writes_it(study):
    schemas = study.root / "graph/extraction/schemas.py"
    schemas.write_text(schemas.read_text().replace("class Profile:", "class HTTPProfile:"))

    result, _ = study.extract("run", "graph/extraction/schemas.py:HTTPProfile", "data/pages")

    assert result.exit_code == 0, result.output
    assert (study.root / "data/extracted/http_profile.jsonl").is_file()
