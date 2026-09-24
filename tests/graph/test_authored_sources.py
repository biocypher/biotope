"""Authored schemas: field coverage, value aliases, freshness and inventory selection."""

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from biotope.graph import Pipeline, SourceContract, Topology
from biotope.graph.check import check_pipeline
from biotope.graph.reports import CheckFailed
from biotope.graph.sources import check_source_record, digest
from biotope.graph.targets import manifest_targets


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
    __source_digest__: ClassVar[str] = {manifest_targets(data)[0].revision!r}
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
    source = SourceContract("source", manifest, schema, (module.Row, module.Facts))
    pipeline = Pipeline(
        "authored",
        Topology((), ()),
        (source,),
        (),
        lambda context: None,
        scope="table and reviewed paper",
        code_paths=(schema, Path(__file__)),
        source_inventory=(source,),
    )
    (tmp_path / "loader.py").write_text("def load(context):\n    return iter(())\n")
    yield data, module, pipeline
    sys.modules.pop(spec.name, None)


def test_definition_check_accepts_renamed_fields_and_class_level_value_aliases(authored, monkeypatch):
    _, module, pipeline = authored
    aliases = {"true": "flagged", "false": "unflagged"}
    monkeypatch.setattr(module.Row, "__value_aliases__", {"expression_state": aliases}, raising=False)
    report = check_pipeline(pipeline, static=False)
    assert report["state"] == "checked"
    assert report["sources"]["source"]["records"] == ["table", "paper/facts"]
    [entry] = [e for e in report["standardization"]["preserved_fields"] if e["attribute"] == "expression_state"]
    assert entry["aliases"] == aliases


@pytest.mark.parametrize(
    "aliases",
    [
        pytest.param({"typo": {"true": "flagged"}}, id="unbound-attribute"),
        pytest.param({"expression_state": {}}, id="empty"),
        pytest.param({"expression_state": {" TRUE ": "flagged"}}, id="untrimmed-token"),
        pytest.param({"expression_state": {"true": 1}}, id="non-string-output"),
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
        pytest.param({"gene_symbol": "table/Gene"}, id="omitted-field"),
        pytest.param({"typo": "table/Gene", "expression_state": "table/low"}, id="unknown-attribute"),
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


def retype_the_first_column(data):
    data["recordSet"][0]["field"][0]["dataType"] = "sc:Integer"


def replace_the_document(data):
    data["distribution"][0]["sha256"] = "different-document"


@pytest.mark.parametrize(("change", "record"), [(retype_the_first_column, "Row"), (replace_the_document, "Facts")])
def test_changed_source_declaration_requires_review(authored, change, record):
    data, module, _ = authored
    change(data)
    with pytest.raises(ValueError, match="stale source binding"):
        check_source_record(data, getattr(module, record))


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


def error_codes(failure: pytest.ExceptionInfo[CheckFailed]) -> set[str]:
    return {f["code"] for f in failure.value.report["findings"] if f["severity"] == "error"}


def test_inventory_requires_selection_or_exclusion_and_rejects_placeholder(authored):
    _, _, pipeline = authored
    source = pipeline.sources[0]
    loader = source.schema.parent / "loader.py"
    loader.write_text("# biotope:placeholder\nraise NotImplementedError\n")
    with pytest.raises(CheckFailed) as failure:
        check_pipeline(pipeline, static=False)
    assert error_codes(failure) == {"inventory.placeholder"}
    loader.write_text('"""Replaced the # biotope:placeholder stub."""\n\ndef load(context):\n    return iter(())\n')
    assert check_pipeline(pipeline, static=False)["excluded_sources"] == {}
    cases = {
        "inventory.conflicting_selection": replace(pipeline, excluded_sources={source.name: "excluded"}),
        "inventory.unknown_exclusion": replace(pipeline, excluded_sources={"unknown": "excluded"}),
        "inventory.unselected": replace(pipeline, sources=()),
        "inventory.exclusion_reason": replace(pipeline, sources=(), excluded_sources={source.name: " "}),
        "inventory.absent": replace(pipeline, source_inventory=()),
        "inventory.mismatch": replace(pipeline, source_inventory=(replace(source, name="renamed"),)),
    }
    for code, case in cases.items():
        with pytest.raises(CheckFailed) as failure:
            check_pipeline(case, static=False)
        assert code in error_codes(failure), (code, failure.value.report["findings"])
    excluded = replace(pipeline, sources=(), excluded_sources={source.name: "Out of scope"})
    assert check_pipeline(excluded, static=False)["excluded_sources"] == {source.name: "Out of scope"}
