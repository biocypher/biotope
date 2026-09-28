"""Shared terms and local bindings: overview, declaration checks and runtime vocabularies."""

from dataclasses import dataclass, field, make_dataclass, replace
from pathlib import Path
from typing import Any, ClassVar, NewType

import pytest

from biotope.graph import Evidence, Pipeline, RunContext, SourceContract, SourceRecord, Term, Topology, source_field
from biotope.graph.sources import check_source_record
from biotope.graph.standardization import describe_standardization, field_bindings, validate_terms
from biotope.graph.targets import manifest_targets


SEX = Term("sex", "Reported sex in a shared vocabulary.", ("male", "female"))


@dataclass(frozen=True)
class Row:
    __record_set__: ClassVar[str] = "table"
    __source_digest__: ClassVar[str] = "reviewed"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({"", "na"})
    sex: str | None = source_field("Sex", term=SEX, aliases={"m": "male", "f": "female"})
    label: str = source_field(missing=frozenset({""}), default="")


def declaring(name: str, annotation: object, binding: Any = None) -> type:
    member = (name, annotation, field() if binding is None else binding)
    return make_dataclass("Declared", [member], namespace={"__record_set__": "table"}, frozen=True)


def test_overview_derives_bindings_and_passthrough_without_a_second_matrix():
    result = describe_standardization((SEX,), (Row,))
    assert field_bindings(Row) == {"sex": "table/Sex", "label": "table/label"}
    [binding] = result["terms"]["sex"]["bindings"]
    assert binding["aliases"] == {"m": "male", "f": "female"}
    assert binding["missing_values"] == ["", "na"]
    [preserved] = result["preserved_fields"]
    assert preserved["source_field"] == "table/label"
    assert preserved["missing_values"] == [""]


@pytest.mark.parametrize(
    ("terms", "record", "message"),
    [
        ((), Row, "unknown or conflicting standard term"),
        ((replace(SEX, description="Different"),), Row, "unknown or conflicting standard term"),
        ((SEX, SEX), Row, "Invalid or duplicate standard term"),
        ((replace(SEX, values=()),), Row, "values must be distinct, nonempty strings"),
        ((SEX,), declaring("sex", str, source_field("Sex", term=SEX, aliases={"m": "man"})), "alias output"),
        ((SEX,), declaring("sex", str | int, source_field("Sex", term=SEX)), "vocabulary requires str"),
        ((SEX,), declaring("gender", str, source_field("Sex", term=SEX)), "standard name must be sex"),
        ((), declaring("label", str, source_field(missing=frozenset({"NA"}))), "invalid missing-value tokens"),
        (
            (SEX,),
            declaring("nested", declaring("other", str, source_field(term=Term("other", "Unregistered", ("a",))))),
            "unknown or conflicting standard term",
        ),
    ],
    ids=[
        "unknown_term",
        "conflicting_term",
        "duplicate_term",
        "empty_vocabulary",
        "alias_outside_vocabulary",
        "vocabulary_on_a_number",
        "field_not_named_after_its_term",
        "uncanonical_missing_token",
        "unregistered_term_in_a_nested_record",
    ],
)
def test_invalid_declarations_are_rejected(terms, record, message):
    with pytest.raises(ValueError, match=message):
        describe_standardization(terms, (record,))


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
    monkeypatch.setattr(Row, "__source_digest__", manifest_targets(data)[0].revision)
    check_source_record(data, Row)

    @dataclass(frozen=True)
    class Duplicate(Row):
        extra: str = source_field("Sex", default="")

    with pytest.raises(ValueError, match="duplicate bindings"):
        check_source_record(data, Duplicate)


def test_loaded_values_must_already_be_standard_and_may_be_missing():
    source = SourceContract("source", Path("manifest.jsonld"), Path(__file__), (Row,))
    context = RunContext(Pipeline("example", Topology((), ()), (source,), (), lambda _: None, "test", (), terms=(SEX,)))
    alias = SourceRecord(Row("m"), (Evidence("table.csv", "sha256:test", "table", "row 1"),))
    with pytest.raises(ValueError, match="'m' is outside sex"):
        list(context.load(source, lambda _: iter((alias,)), None))
    validate_terms(Row(None))


def test_terms_and_vocabularies_are_checked_inside_nested_records():
    @dataclass(frozen=True)
    class Nested:
        __record_set__: ClassVar[str] = "rows/nested"
        sex: str = source_field(term=SEX)

    @dataclass(frozen=True)
    class Outer:
        __record_set__: ClassVar[str] = "rows"
        nested: Nested
        repeated: list[Nested] | None = None

    overview = describe_standardization((SEX,), (Outer,))
    assert [binding["record_set"] for binding in overview["terms"]["sex"]["bindings"]] == ["rows/nested"]
    validate_terms(Outer(Nested("male"), [Nested("female")]))
    with pytest.raises(ValueError, match=r"Outer\.nested\.sex: 'invalid' is outside sex"):
        validate_terms(Outer(Nested("invalid")))
    with pytest.raises(ValueError, match=r"Outer\.repeated\[1\]\.sex"):
        validate_terms(Outer(Nested("male"), [Nested("male"), Nested("invalid")]))


@pytest.mark.parametrize("attribute", ["__file_object__", "__file_set__"])
def test_document_facts_bind_shared_terms_like_table_records(attribute):
    @dataclass(frozen=True)
    class Finding:
        sex: str = source_field(term=SEX)

    @dataclass(frozen=True, kw_only=True)
    class Facts:
        __record_set__: ClassVar[str] = "doc/facts"
        sex: str = source_field(term=SEX)
        finding: Finding

    setattr(Facts, attribute, "doc")
    bindings = describe_standardization((SEX,), (Facts,))["terms"]["sex"]["bindings"]
    assert [(binding["record_set"], binding["source_field"]) for binding in bindings] == [
        ("doc/facts", "doc/facts/sex"),
        ("doc/facts/finding", "doc/facts/finding/sex"),
    ]
    for terms in ((), (replace(SEX, description="A conflicting meaning."),)):
        with pytest.raises(ValueError, match="unknown or conflicting standard term"):
            describe_standardization(terms, (Facts,))


def test_a_vocabulary_binds_fields_that_hold_one_string():
    Label = NewType("Label", str)

    @dataclass(frozen=True)
    class Named:
        sex: Label | None = source_field(term=SEX)

    @dataclass(frozen=True)
    class Listed:
        sex: list[str] = source_field(term=SEX)

    assert describe_standardization((SEX,), (Named,))["terms"]["sex"]["bindings"]
    with pytest.raises(ValueError, match=r"vocabulary requires str or str \| None"):
        describe_standardization((SEX,), (Listed,))
