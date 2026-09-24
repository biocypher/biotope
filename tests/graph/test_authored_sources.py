"""Authored schemas retain source coverage and freshness without raw text equality."""

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from biotope.graph import Pipeline, SourceContract, Topology
from biotope.graph.check import check_pipeline
from biotope.graph.reports import CheckFailed
from biotope.graph.sources import check_source_record, contract_digests, digest


@pytest.fixture
def authored(tmp_path):
    data = {
        "recordSet": [
            {
                "@id": "table",
                "field": [
                    {"@id": "table/Gene", "name": "Gene", "dataType": "sc:Text"},
                    {"@id": "table/low", "name": "low", "dataType": "sc:Boolean"},
                ],
            }
        ],
        "distribution": [{"@id": "paper", "@type": "cr:FileObject", "contentUrl": "paper.pdf", "sha256": "reviewed"}],
    }
    manifest = tmp_path / "source.jsonld"
    manifest.write_text(json.dumps(data))
    schema = tmp_path / "schema.py"
    schema.write_text(f"""
from dataclasses import dataclass
from typing import ClassVar

@dataclass(frozen=True)
class Row:
    __record_set__: ClassVar[str] = "table"
    __source_digest__: ClassVar[str] = {contract_digests(data)["table"]!r}
    __field_refs__: ClassVar[dict[str, str]] = {{"gene_symbol": "table/Gene", "expression_state": "table/low"}}
    gene_symbol: str
    expression_state: str

@dataclass(frozen=True)
class Facts:
    __file_object__: ClassVar[str] = "paper"
    __record_set__: ClassVar[str] = "paper/facts"
    __source_digest__: ClassVar[str] = {digest({"@context": None, "distribution": data["distribution"][0]})!r}
    sample_count: int
""")
    spec = importlib.util.spec_from_file_location("authored_source_test", schema)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    pipeline = Pipeline(
        "authored",
        Topology((), ()),
        (SourceContract("source", manifest, schema, (module.Row, module.Facts)),),
        (),
        lambda context: None,
        scope="table and reviewed paper",
        code_paths=(schema, Path(__file__)),
    )
    yield data, module, pipeline
    sys.modules.pop(spec.name, None)


def test_definition_check_accepts_renamed_fields_and_standardized_value_types(authored):
    _, _, pipeline = authored
    report = check_pipeline(pipeline, static=False)
    assert report["state"] == "checked"
    assert report["sources"]["source"]["records"] == ["table", "paper/facts"]


def test_value_aliases_can_be_supplied_by_a_shared_protocol(authored, monkeypatch):
    _, module, pipeline = authored
    monkeypatch.setattr(
        module.Row, "__value_aliases__", {"expression_state": {"true": "flagged", "false": "unflagged"}}, raising=False
    )
    assert check_pipeline(pipeline, static=False)["state"] == "checked"


@pytest.mark.parametrize(
    "aliases",
    [
        {"typo": {"true": "flagged"}},
        {"expression_state": {}},
        {"expression_state": {" TRUE ": "flagged"}},
        {"expression_state": {"true": 1}},
    ],
)
def test_invalid_value_policy_blocks_definition_check(authored, monkeypatch, aliases):
    _, module, pipeline = authored
    monkeypatch.setattr(module.Row, "__value_aliases__", aliases, raising=False)
    with pytest.raises(CheckFailed) as failure:
        check_pipeline(pipeline, static=False)
    assert any(
        f["code"] == "source.contract" and "value aliases" in f["message"] for f in failure.value.report["findings"]
    )


@pytest.mark.parametrize(
    "bindings",
    [
        {"gene_symbol": "table/Gene"},  # A described field was silently omitted.
        {"gene_symbol": "other/Gene", "expression_state": "table/low"},
        {"typo": "table/Gene", "expression_state": "table/low"},
    ],
)
def test_bad_field_coverage_blocks_definition_check(authored, monkeypatch, bindings):
    _, module, pipeline = authored
    monkeypatch.setattr(module.Row, "__field_refs__", bindings)
    with pytest.raises(CheckFailed) as failure:
        check_pipeline(pipeline, static=False)
    assert any(
        f["code"] == "source.contract" and "field coverage" in f["message"] for f in failure.value.report["findings"]
    )


@pytest.mark.parametrize("source", ["table", "paper"])
def test_changed_source_declaration_requires_review(authored, source):
    data, module, _ = authored
    if source == "table":
        data["recordSet"][0]["field"][0]["dataType"] = "sc:Integer"
        record = module.Row
    else:
        data["distribution"][0]["sha256"] = "different-document"
        record = module.Facts
    with pytest.raises(ValueError, match="stale source binding"):
        check_source_record(data, record)


def test_missing_document_and_foreign_fact_identity_are_rejected(authored, monkeypatch):
    data, module, _ = authored
    monkeypatch.setattr(module.Facts, "__record_set__", "other/facts")
    with pytest.raises(ValueError, match="scoped under"):
        check_source_record(data, module.Facts)
    data["distribution"] = []
    with pytest.raises(ValueError, match="missing or ambiguous"):
        check_source_record(data, module.Facts)


def test_empty_record_registration_is_not_validated_as_a_source(authored):
    _, _, pipeline = authored
    empty = replace(pipeline.sources[0], records=())
    with pytest.raises(CheckFailed) as failure:
        check_pipeline(replace(pipeline, sources=(empty,)), static=False)
    assert any("at least one source record" in f["message"] for f in failure.value.report["findings"])


def test_inventory_requires_selection_or_exclusion_and_rejects_placeholder(authored):
    _, _, pipeline = authored
    source = pipeline.sources[0]
    loader = source.schema.parent / "loader.py"
    loader.write_text("# biotope:placeholder\nraise NotImplementedError\n")
    selected = replace(pipeline, source_inventory=(source,))
    with pytest.raises(CheckFailed) as failure:
        check_pipeline(selected, static=False)
    assert any(
        f["code"] == "inventory.invalid" and "placeholder" in f["message"] for f in failure.value.report["findings"]
    )
    loader.write_text("def load(context):\n    return iter(())\n")
    assert check_pipeline(selected, static=False)["excluded_sources"] == {}
    for exclusions in ({source.name: "excluded"}, {"unknown": "excluded"}):
        with pytest.raises(CheckFailed):
            check_pipeline(replace(selected, excluded_sources=exclusions), static=False)
    excluded = replace(selected, sources=(), excluded_sources={source.name: "Out of scope"})
    assert check_pipeline(excluded, static=False)["excluded_sources"] == {source.name: "Out of scope"}


def test_inventory_detects_missing_record_set(authored):
    _, module, pipeline = authored
    facts_only = replace(pipeline.sources[0], records=(module.Facts,))
    selected = replace(pipeline, sources=(facts_only,), source_inventory=(facts_only,))
    (facts_only.schema.parent / "loader.py").write_text("def load(context):\n    return iter(())\n")
    with pytest.raises(CheckFailed) as failure:
        check_pipeline(selected, static=False)
    assert any(
        f["code"] == "inventory.invalid" and "missing record sets" in f["message"]
        for f in failure.value.report["findings"]
    )
