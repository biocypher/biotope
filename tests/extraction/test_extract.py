import json
import re
import shutil
import subprocess

import pytest
from conftest import FIXTURES, KEY, LIVE_KEY, ROUNDS, ROWS, funding_round

from biotope.extraction import Schema


PROFILE = "extraction/schemas.py:Profile"
ROUND = "extraction/schemas.py:FundingRound"
LIND = "data/pages/lind.html"
OKAFOR = "data/pages/okafor.html"
CALL = "data/calls/call.pdf"


def squeeze(text):
    return re.sub(r"[\s\-‐-―−­]+", "", text).lower()


def statuses(report):
    return {document["path"]: document["status"] for document in report["documents"]}


def test_run_stores_records_with_evidence_and_registers_them(study):
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"}
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
            if evidence["aligned"]:
                assert squeeze(text[evidence["start"] : evidence["end"]]) == squeeze(evidence["quote"])
                assert evidence["page"] is None
    unaligned = okafor["values"]["group"]
    assert unaligned["value"] == "Machine Learning for Tissues Group"
    assert unaligned["evidence"]["aligned"] is False and unaligned["evidence"]["start"] is None
    assert report["unaligned"] == [{"record": OKAFOR, "field": "group", "quote": "Machine Learning for Tissues Lab"}]
    assert sorted(report["appeared"]) == [LIND, OKAFOR] and report["disappeared"] == []

    result, report = study.extract("run", ROUND, "data/calls")
    assert result.exit_code == 0, result.output
    rounds = {record["id"]: record for record in study.records("funding_round")}
    full = rounds['data/calls/call.pdf#round="Full proposal"']
    evidence = full["values"]["deadline"]["evidence"]
    assert evidence["quote"] == ROWS["Full proposal"] and evidence["aligned"] is True and evidence["page"] == 2
    assert study.text(CALL).count("\f") == 1

    manifest = json.loads((study.root / ".biotope/datasets/extracted/profile.jsonld").read_text())
    assert manifest["biotope:status"] == "processed"
    assert manifest["prov:wasDerivedFrom"] == [{"@id": "data/pages"}]
    descriptions = {}

    def collect(fields):
        for item in fields:
            descriptions[item["@id"]] = item.get("description")
            collect(item.get("subField", []))

    collect(manifest["recordSet"][0]["field"])
    assert descriptions["profile.jsonl/values/name/value"] == "The researcher's full name, without academic titles."
    assert descriptions["profile.jsonl/values/methods/value"] == (
        "Each experimental or computational method the page lists."
    )
    generated = study.run("source", "generate", ".biotope/datasets/extracted/profile.jsonld", "--out", "graph/sources")
    assert generated.exit_code == 0, generated.output
    schema = next((study.root / "graph/sources").rglob("schema.py")).read_text()
    assert "UnknownValue" not in schema and re.search(r"methods: list\[\w+ \| None\]", schema)

    texts = [str(path.relative_to(study.root)) for path in (study.root / ".biotope/texts").glob("*.txt")]
    assert len(texts) == 3
    ignored = subprocess.run(["git", "check-ignore", *texts], cwd=study.root, capture_output=True, text=True)
    assert sorted(ignored.stdout.split()) == sorted(texts)
    tracked = ["extracted/profile.jsonl", ".biotope/datasets/extracted/profile.jsonld"]
    assert subprocess.run(["git", "check-ignore", *tracked], cwd=study.root).returncode == 1


def test_run_reuses_stored_records_until_an_input_changes(study):
    assert study.extract("run", PROFILE, "data/pages")[0].exit_code == 0
    sent = len(study.endpoint.requests)
    before = study.snapshot()
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0 and len(study.endpoint.requests) == sent
    assert statuses(report) == {LIND: "reused", OKAFOR: "reused"} and study.snapshot() == before
    shutil.rmtree(study.root / ".biotope/texts")
    before = study.snapshot()
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0 and len(study.endpoint.requests) == sent and study.snapshot() == before

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
        lambda: (study.root / "extraction/schemas.py").write_text(
            (study.root / "extraction/schemas.py").read_text().replace("without academic titles", "as written")
        ),
    ]
    for change in changes:
        change()
        sent = len(study.endpoint.requests)
        result, report = study.extract("run", PROFILE, "data/pages")
        assert result.exit_code == 0, result.output
        assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"}
        assert len(study.endpoint.requests) == sent + 2
    assert study.endpoint.requests[-1]["path"] == "/v2/chat/completions"

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


def test_failed_missing_and_removed_documents(study):
    study.endpoint.reply("Chidi Okafor", 400)
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code != 0
    assert statuses(report) == {LIND: "extracted", OKAFOR: "failed"}
    assert "400" in report["documents"][1]["reason"]
    assert [record["id"] for record in study.records("profile")] == [LIND]

    (study.root / OKAFOR).unlink()
    rebaked = study.run("add", "data/pages", "--rebake")
    assert rebaked.exit_code == 0, rebaked.output
    (study.root / LIND).unlink()
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code != 0
    assert statuses(report) == {LIND: "missing"}
    assert [record["id"] for record in study.records("profile")] == [LIND]

    shutil.copy(FIXTURES / "lind.html", study.root / LIND)
    shutil.copy(FIXTURES / "okafor.html", study.root / OKAFOR)
    assert study.run("add", "data/pages", "--rebake").exit_code == 0
    study.endpoint.reply("Chidi Okafor", {"records": []})
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0 and statuses(report) == {LIND: "reused", OKAFOR: "extracted"}
    (study.root / LIND).unlink()
    rebaked = study.run("add", "data/pages", "--rebake")
    assert rebaked.exit_code == 0, rebaked.output
    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    assert report["disappeared"] == [LIND] and statuses(report) == {OKAFOR: "reused"}
    assert study.records("profile") == []


def test_a_project_extractor_runs_by_configuration(study):
    (study.root / "extraction/rules.py").write_text(
        (FIXTURES / "rules.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    study.configure(extractor="extraction/rules.py:LineExtractor", version="1", line=2)
    tried = study.run("extract", "try", PROFILE, LIND)
    assert tried.exit_code == 0, tried.output
    assert "Mara Lind" in tried.output and "line 2" in tried.output

    result, report = study.extract("run", PROFILE, "data/pages")
    assert result.exit_code == 0, result.output
    lind = study.records("profile")[0]
    assert lind["values"]["name"]["value"] == "Dr. Mara Lind"
    assert lind["values"]["name"]["evidence"]["locator"] == "line 2"
    assert lind["provenance"]["extractor"] == {"name": "lines", "version": "1", "settings": {"line": 2}}

    study.configure(extractor="extraction/rules.py:LineExtractor", version="2", line=2)
    result, report = study.extract("run", PROFILE, "data/pages")
    assert statuses(report) == {LIND: "extracted", OKAFOR: "extracted"}
    assert study.endpoint.requests == []


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
    assert rounds.exit_code == 0
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

    (study.root / "extraction/schemas.py").write_text(
        source.replace("    methods: list[str]", "    links: dict[str, str]")
    )
    result = study.run("extract", "try", PROFILE, LIND)
    assert result.exit_code != 0 and "links" in result.output
    assert study.endpoint.requests == []


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
    aligned = sum(item["evidence"]["aligned"] for item in values)
    print(f"aligned {aligned} of {len(values)} non-null values ({aligned / len(values):.0%})")
    assert aligned >= 0.9 * len(values)
    full = next(
        record
        for record in study.records("funding_round")
        if "Full proposal" in str(record["values"]["round"]["value"])
    )
    evidence = full["values"]["deadline"]["evidence"]
    assert evidence["page"] == 2 and squeeze(ROWS["Full proposal"]) in squeeze(evidence["quote"])
