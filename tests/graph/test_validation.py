"""Project checks, stage accounting, and the silent-loss gap they exist to close."""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from typing import ClassVar, NewType

import pytest

from biotope.graph import (
    Audit,
    Capability,
    Evidence,
    GraphView,
    Mapping,
    Pipeline,
    QueryContext,
    SourceRecord,
    Topology,
    ValidationCheck,
    ValidationResult,
    build,
)
from biotope.graph.runtime import RunContext


ItemId = NewType("ItemId", str)

# Two source rows are eligible. A pipeline that emits one and reports nothing is
# the failure this module is about, so the expectation lives here, beside the data.
SOURCE_ROWS = ({"key": "a", "eligible": True}, {"key": "b", "eligible": True})


@dataclass(frozen=True)
class ItemRow:
    """A synthetic source row standing in for one eligible observation."""

    key: str


@dataclass(frozen=True)
class Item:
    """One retained observation."""

    schema_id: ClassVar[str] = "test:item"
    id: ItemId
    tags: list[str] = field(default_factory=list[str])


def make_item(row: SourceRecord[ItemRow]) -> Iterator[Item]:
    """Carry one row into the graph."""
    yield Item(ItemId("item:" + row.value.key), [row.value.key])


ITEMS = Mapping(name="items", function=make_item)


def emit(context: RunContext, keys: tuple[str, ...]) -> None:
    """Emit only the named keys, exactly as a pipeline with a bare `continue` would."""
    for key in keys:
        context.map(ITEMS, SourceRecord(ItemRow(key), (Evidence("rows", "v1", "items", key),)))


def eligible_rows_are_present(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
    """Compare the graph with an expectation derived from the source, not the pipeline."""
    expected = {"item:" + row["key"] for row in SOURCE_ROWS if row["eligible"]}
    found = {item.id for item in view.records(Item)}
    if found != expected:
        return ValidationResult.wrong(f"Missing {sorted(expected - found)}", expected=len(expected), found=len(found))
    return ValidationResult.ok(f"All {len(expected)} eligible rows are present.")


CHECK = ValidationCheck(
    name="test:eligible-rows-present",
    function=eligible_rows_are_present,
    capability="count-items",
    evidence=("Expectation read from the source table.",),
)

CONTEXT = QueryContext(
    capabilities=(
        Capability(key="count-items", question="How many eligible items are there?", concepts=("test:item",)),
    )
)

PIPELINE = Pipeline(
    "loss",
    Topology((Item,), ()),
    (),
    (ITEMS,),
    lambda context: emit(context, ("a", "b")),
    scope="every eligible row",
    code_paths=(__file__,),
    validation_checks=(CHECK,),
    query_context=CONTEXT,
)


def unchecked(pipeline: Pipeline) -> Pipeline:
    """The same pipeline as an existing project would have it: no declared checks."""
    return replace(pipeline, validation_checks=(), query_context=QueryContext())


class Writer:
    """A writer that records whether the export boundary was ever reached."""

    def __init__(self) -> None:
        self.wrote = False

    def check_environment(self) -> dict[str, object]:
        return {"exporter": "test", "version": "0", "format": "none"}

    def write(self, context: RunContext, directory: object, *, query_context: dict[str, object]) -> list[str]:
        self.wrote = True
        return []


def test_structural_checks_alone_cannot_see_a_dropped_record(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})
    dropped = replace(unchecked(PIPELINE), run=lambda context: emit(context, ("a",)))
    writer = Writer()

    # Reproduce the gap exactly: one retained node, no exclusions, quality complete.
    report = build.run_pipeline(dropped, tmp_path / "silent", writer=writer)
    assert writer.wrote and report["state"] == "complete"
    assert report["graph_objects"] == {"nodes": 1, "edges": 0}
    assert [f for f in report["findings"] if f.get("kind") == "exclusion"] == []
    assert report["quality"]["state"] == "complete" and report["quality"]["findings"] == []

    # Nothing structural failed, so the absence of checks is itself the finding.
    assert report["validation"]["state"] == "absent"
    assert report["validation"]["checks"] == []
    assert [f["code"] for f in report["validation"]["findings"]] == ["validation.absent"]


def test_declared_check_catches_the_loss_and_blocks_export(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})
    dropped = replace(PIPELINE, run=lambda context: emit(context, ("a",)))
    writer = Writer()
    with pytest.raises(build.RunFailed) as failure:
        build.run_pipeline(dropped, tmp_path / "caught", writer=writer)
    report = failure.value.report
    assert not writer.wrote, "a contradicted expectation must block the export"
    assert report["state"] == "failed"
    assert report["validation"]["state"] == "failed"
    check = report["validation"]["checks"][0]
    assert check["name"] == CHECK.name and check["measurements"] == {"expected": 2, "found": 1}
    assert "item:b" in check["detail"]
    assert report["validation"]["capabilities"]["count-items"]["state"] == "failed"
    # Measurements still ran, so a blocked export is diagnosable rather than blank.
    assert report["quality"]["state"] == "complete"
    assert json.loads((tmp_path / "caught/run.json").read_text())["validation"]["state"] == "failed"

    complete = Writer()
    passing = build.run_pipeline(PIPELINE, tmp_path / "complete", writer=complete)
    assert complete.wrote and passing["validation"]["state"] == "passed"
    assert passing["validation"]["capabilities"]["count-items"]["state"] == "supported"


def test_unverified_leaves_one_capability_unresolved_and_keeps_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})

    def unknowable(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
        return ValidationResult.unknown("The source does not state the contrast direction.")

    def broken(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
        raise RuntimeError("check is broken")

    pipeline = replace(
        PIPELINE,
        validation_checks=(
            CHECK,
            ValidationCheck(name="test:direction", function=unknowable, capability="direction"),
        ),
        query_context=replace(
            CONTEXT,
            capabilities=(
                *CONTEXT.capabilities,
                Capability(key="direction", question="Which way does the effect point?"),
                Capability(key="untested", question="Something nothing checks."),
            ),
        ),
    )
    writer = Writer()
    report = build.run_pipeline(pipeline, tmp_path / "partial", writer=writer)
    assert writer.wrote, "missing knowledge must not discard the capabilities that do work"
    assert report["validation"]["state"] == "unverified"
    states = {k: v["state"] for k, v in report["validation"]["capabilities"].items()}
    assert states == {"count-items": "supported", "direction": "unverified", "untested": "unchecked"}
    codes = {f["code"] for f in report["validation"]["findings"]}
    assert codes == {"validation.unverified", "validation.unchecked_capability"}

    # A check that cannot run has not passed.
    failing = replace(pipeline, validation_checks=(ValidationCheck("test:broken", broken, "count-items"),))
    with pytest.raises(build.RunFailed) as failure:
        build.run_pipeline(failing, tmp_path / "broken", writer=Writer())
    detail = failure.value.report["validation"]["checks"][0]
    assert detail["state"] == "failed" and "check is broken" in detail["detail"]


def test_audits_record_stage_accounting_without_imposing_arithmetic(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})

    def run(context: RunContext) -> None:
        emit(context, ("a", "b"))
        # One row read twice, several rows folded into one object, and a join that
        # could not be attempted: none of these totals relate by a fixed equation.
        context.record_audit(
            "read:items",
            inputs="one row per key, read once for identity and once for values",
            outputs="one Item per distinct key",
            selection="Keep every eligible row.",
            counts={"reads": 4, "distinct_keys": 2, "items": 2},
            evidence=(Evidence("rows", "v1", "items", "a"),),
        )
        context.record_audit(
            "join:annotations",
            inputs="one Item per key",
            outputs="one annotation edge per resolved key",
            selection="Join only where the reference table supplies an identifier.",
            counts={"items": 2, "resolved": 0, "unresolvable": 2},
            notes=("Unresolved keys limit the join; the items themselves are retained.",),
        )

    report = build.run_pipeline(replace(unchecked(PIPELINE), run=run), tmp_path / "audit", writer=Writer())
    stages = {item["stage"]: item for item in report["audits"]}
    assert set(stages) == {"read:items", "join:annotations"}
    assert stages["read:items"]["counts"] == {"reads": 4, "distinct_keys": 2, "items": 2}
    assert stages["read:items"]["evidence_sample"][0]["location"] == "a"
    assert stages["join:annotations"]["counts"]["unresolvable"] == 2
    assert report["graph_objects"]["nodes"] == 2, "an unavailable join does not remove a retained record"
    assert report["loaded_records"] == {}

    context = RunContext(PIPELINE)
    context.record_audit("s", inputs="i", outputs="o", selection="all", counts={})
    with pytest.raises(ValueError, match="already recorded"):
        context.record_audit("s", inputs="i", outputs="o", selection="all", counts={})
    with pytest.raises(ValueError, match="non-empty selection"):
        context.record_audit("t", inputs="i", outputs="o", selection=" ", counts={})
    with pytest.raises(ValueError, match="non-negative integer"):
        context.record_audit("u", inputs="i", outputs="o", selection="all", counts={"n": -1})


def test_a_check_cannot_change_the_graph_that_is_exported(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *a, **kw: {"state": "checked"})

    def rewrite_a_record(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
        view.nodes["item:a"].value = Item(ItemId("item:elsewhere"))
        return ValidationResult.ok("Reported success after rewriting a record.")

    def append_to_a_list(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
        next(iter(view.nodes.values())).value.tags.append("added")
        return ValidationResult.ok("Reported success after mutating a list property.")

    def copy_then_mutate(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
        for item in view.records(Item):
            item.tags.append("harmless")
        return ValidationResult.ok("Mutated only the copies records() hands out.")

    for name, function in (("test:rewrite", rewrite_a_record), ("test:append", append_to_a_list)):
        writer = Writer()
        pipeline = replace(PIPELINE, validation_checks=(ValidationCheck(name, function, "count-items"),))
        with pytest.raises(build.RunFailed) as failure:
            build.run_pipeline(pipeline, tmp_path / name.replace(":", "-"), writer=writer)
        assert not writer.wrote, "a mutated graph must never reach the writer"
        assert "modified the graph" in failure.value.report["error"]

    # The documented access path hands out copies, so the graph is untouched.
    writer = Writer()
    pipeline = replace(PIPELINE, validation_checks=(ValidationCheck("test:copies", copy_then_mutate, "count-items"),))
    report = build.run_pipeline(pipeline, tmp_path / "copies", writer=writer)
    assert writer.wrote and report["validation"]["state"] == "passed"

    context = RunContext(PIPELINE)
    emit(context, ("a",))
    with pytest.raises(TypeError):
        context.view().nodes["item:b"] = context.nodes["item:a"]
