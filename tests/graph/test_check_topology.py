"""Topology findings: what a consumer of the export can and cannot read from it."""

from dataclasses import dataclass, field
from typing import ClassVar, NewType

from biotope.graph import Pipeline, Topology
from biotope.graph.check import check_pipeline


DescribedId = NewType("DescribedId", str)
BareId = NewType("BareId", str)
PlaceholderId = NewType("PlaceholderId", str)
CompleteId = NewType("CompleteId", str)


@dataclass(frozen=True)
class Described:
    """A concept with authored meaning."""

    schema_id: ClassVar[str] = "check:described"
    id: DescribedId
    score: float = field(metadata={"description": "Mean score over three replicates."})
    note: str


@dataclass(frozen=True)
class Bare:
    schema_id: ClassVar[str] = "check:bare"
    id: BareId


@dataclass(frozen=True)
class Placeholder:
    """An illustrative concept that a real project replaces."""

    schema_id: ClassVar[str] = "example:placeholder"
    id: PlaceholderId


@dataclass(frozen=True)
class Complete:
    """Every property carries its meaning."""

    schema_id: ClassVar[str] = "check:complete"
    id: CompleteId
    score: float = field(metadata={"description": "Mean score over three replicates."})


def check(*nodes: type) -> dict[str, dict[str, object]]:
    pipeline = Pipeline(
        "topology", Topology(nodes, ()), (), (), lambda context: None, scope="definitions", code_paths=(__file__,)
    )
    report = check_pipeline(pipeline, static=False)
    return {finding["code"]: finding for finding in report["findings"] if finding["code"].startswith("topology.")}


def test_undescribed_and_example_concepts_are_warned_about_and_a_complete_topology_is_not():
    found = check(Described, Bare, Placeholder)
    assert {code: finding["severity"] for code, finding in found.items()} == {
        "topology.undescribed": "warning",
        "topology.undescribed_property": "warning",
        "topology.examples": "warning",
    }
    assert "check:bare" in found["topology.undescribed"]["message"]
    assert "check:described" not in found["topology.undescribed"]["message"]
    assert "check:described.note" in found["topology.undescribed_property"]["message"]
    assert "check:described.score" not in found["topology.undescribed_property"]["message"]
    assert "example:placeholder" in found["topology.examples"]["message"]
    assert "check:described" not in found["topology.examples"]["message"]
    assert check(Complete) == {}
