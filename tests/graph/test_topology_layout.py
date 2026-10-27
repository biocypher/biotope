import json
import shutil
import subprocess
import sys

from typed_example import prepare


TISSUE = '''
TissueId = NewType("TissueId", str)


@dataclass(frozen=True)
class Tissue:
    """A tissue a sample was taken from."""

    schema_id: ClassVar[str] = "example:tissue"
    id: TissueId
'''

HAS_TISSUE = '''from dataclasses import dataclass
from typing import ClassVar

from ..sample.node import SampleId
from ..tissue.node import TissueId


@dataclass(frozen=True)
class HasTissue:
    """The sample was taken from this tissue."""

    schema_id: ClassVar[str] = "example:has-tissue"
    source: SampleId
    target: TissueId
'''

HELPERS = """from typing import NewType


Label = NewType("Label", str)


def label(text: str) -> Label:
    return Label(text.strip())
"""


REGISTRY = """from biotope.graph import Topology

from .person.node import Person
from .sample.from_person import FromPerson
from .sample.node import Sample
from .{has_tissue}.has_tissue import HasTissue
from .{tissue}.node import Tissue


TOPOLOGY = Topology(nodes=(Sample, Person, Tissue), edges=(FromPerson, HasTissue))
"""


def check(root):
    result = subprocess.run(
        [sys.executable, "-m", "biotope.cli", "graph", "check", "--json"], cwd=root, text=True, capture_output=True
    )
    report = json.loads(result.stdout)
    return report["state"], {f["subject"]: f["message"] for f in report["findings"] if f["code"] == "topology.layout"}


def test_graph_check_enforces_the_topology_layout_and_leaves_helpers_free(tmp_path):
    root = prepare(tmp_path)
    topology = root / "graph/topology"
    (topology / "tissue").mkdir()
    (topology / "tissue/__init__.py").write_text("")
    (topology / "tissue/node.py").write_text(
        "from dataclasses import dataclass\nfrom typing import ClassVar, NewType\n\n" + TISSUE
    )
    (topology / "shared.py").write_text(HELPERS)
    (topology / "sample/helpers.py").write_text(HELPERS)
    (topology / "sample/has_tissue.py").write_text(HAS_TISSUE)
    registry = topology / "__init__.py"
    registry.write_text(REGISTRY.format(tissue="tissue", has_tissue="sample"))
    shutil.rmtree(root / "raw")
    assert check(root) == ("checked", {})

    shutil.rmtree(topology / "tissue")
    sample = topology / "sample/node.py"
    sample.write_text(sample.read_text() + TISSUE)
    (topology / "sample/has_tissue.py").unlink()
    (topology / "person/has_tissue.py").write_text(HAS_TISSUE.replace("..tissue.node", "..sample.node"))
    registry.write_text(REGISTRY.format(tissue="sample", has_tissue="person"))
    state, misplaced = check(root)
    assert state == "failed"
    assert misplaced == {
        "Tissue": "Tissue: a node class belongs in graph/topology/tissue/node.py",
        "HasTissue": (
            "HasTissue: an edge class belongs in graph/topology/sample/has_tissue.py, its source node's folder"
        ),
    }
