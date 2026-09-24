"""Shared terms and local bindings must remain inspectable and fail on drift."""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import ClassVar

import pytest

from biotope.graph import Evidence, Pipeline, RunContext, SourceContract, SourceRecord, Term, Topology, source_field
from biotope.graph.sources import check_source_record, contract_digests
from biotope.graph.standardization import describe_standardization, field_bindings, validate_terms


SEX = Term("sex", "Reported sex in a shared vocabulary.", ("male", "female"))


@dataclass(frozen=True)
class Row:
    __record_set__: ClassVar[str] = "table"
    __source_digest__: ClassVar[str] = "reviewed"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({""})
    sex: str | None = source_field("Sex", term=SEX, aliases={"m": "male", "f": "female"})
    label: str = ""


def test_overview_derives_bindings_and_passthrough_without_a_second_matrix():
    result = describe_standardization((SEX,), (Row,))
    assert field_bindings(Row) == {"sex": "table/Sex", "label": "table/label"}
    assert result["terms"]["sex"]["bindings"][0]["aliases"] == {"m": "male", "f": "female"}
    assert result["preserved_fields"][0]["source_field"] == "table/label"
    assert result["preserved_fields"][0]["missing_values"] == [""]


def test_unknown_conflicting_and_duplicate_terms_fail():
    for terms in ((), (replace(SEX, description="Different"),), (SEX, SEX)):
        with pytest.raises(ValueError):
            describe_standardization(terms, (Row,))


def test_alias_outputs_must_belong_to_the_vocabulary():
    @dataclass(frozen=True)
    class Wrong:
        __record_set__: ClassVar[str] = "table"
        sex: str = source_field("Sex", term=SEX, aliases={"m": "man"})

    with pytest.raises(ValueError, match="alias output"):
        describe_standardization((SEX,), (Wrong,))


def test_vocabulary_fields_cannot_mix_numeric_and_text_types():
    @dataclass(frozen=True)
    class Wrong:
        __record_set__: ClassVar[str] = "table"
        sex: str | int = source_field("Sex", term=SEX)

    with pytest.raises(ValueError, match="requires str"):
        describe_standardization((SEX,), (Wrong,))


def test_names_and_field_specific_missing_rules_are_checked():
    @dataclass(frozen=True)
    class Wrong:
        __record_set__: ClassVar[str] = "table"
        gender: str = source_field("Sex", term=SEX)

    with pytest.raises(ValueError, match="standard name"):
        describe_standardization((SEX,), (Wrong,))

    @dataclass(frozen=True)
    class Local:
        __record_set__: ClassVar[str] = "table"
        __missing_values__: ClassVar[frozenset[str]] = frozenset({"", "na"})
        label: str = source_field(missing=frozenset({""}))

    assert describe_standardization((), (Local,))["preserved_fields"][0]["missing_values"] == [""]


def test_complete_coverage_rejects_one_source_field_bound_twice(monkeypatch):
    data = {
        "recordSet": [
            {
                "@id": "table",
                "field": [
                    {"@id": "table/Sex", "name": "Sex", "dataType": "sc:Text"},
                    {"@id": "table/label", "name": "label", "dataType": "sc:Text"},
                ],
            }
        ]
    }
    monkeypatch.setattr(Row, "__source_digest__", contract_digests(data)["table"])
    check_source_record(data, Row)

    @dataclass(frozen=True)
    class Duplicate(Row):
        extra: str = source_field("Sex", default="")

    with pytest.raises(ValueError, match="duplicate bindings"):
        check_source_record(data, Duplicate)


def test_runtime_checks_vocabulary_without_parsing_and_tracks_empty_loads():
    source = SourceContract("source", Path("manifest.jsonld"), Path(__file__), (Row,))
    pipeline = Pipeline("example", Topology((), ()), (source,), (), lambda _: None, "test", (), terms=(SEX,))
    context = RunContext(pipeline)
    evidence = (Evidence("table.csv", "sha256:test", "table", "row 1"),)

    def bad(_):
        yield SourceRecord(Row("m"), evidence)

    with pytest.raises(ValueError, match="outside sex"):
        list(context.load(source, bad, None))
    assert not context.completed_sources
    assert list(context.load(source, lambda _: iter(()), None)) == []
    assert context.loaded == {"source": 0}
    assert context.completed_sources == {"source"}
    validate_terms(Row(None))
    validate_terms(Row("male"))


def test_partially_consumed_loader_does_not_count_as_complete():
    source = SourceContract("source", Path("manifest.jsonld"), Path(__file__), (Row,))
    pipeline = Pipeline("example", Topology((), ()), (source,), (), lambda _: None, "test", ())
    context = RunContext(pipeline)
    evidence = (Evidence("table.csv", "sha256:test", "table", "row 1"),)
    records = context.load(source, lambda _: iter((SourceRecord(Row("male"), evidence),)), None)
    next(records)
    assert context.loaded == {"source": 1}
    assert not context.completed_sources
    assert list(records) == []
    assert context.completed_sources == {"source"}
