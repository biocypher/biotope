from pathlib import Path

from biotope.croissant.alignment.model import (
    Alignment,
    Equivalence,
    EquivalenceKind,
    JoinKeys,
    Reference,
)
from biotope.croissant.api import propose_alignment, propose_mapping


def test_alignment_model_validates() -> None:
    alignment = Alignment(
        mappings=["a.mapping.yaml", "b.mapping.yaml"],
        equivalences=[
            Equivalence(
                a=Reference(mapping="a", node_type="gene"),
                b=Reference(mapping="b", node_type="tf"),
                kind=EquivalenceKind.SAME_NODE,
                join_on=JoinKeys(a="ensembl_id", b="ensembl_id"),
            ),
        ],
    )
    assert alignment.equivalences[0].kind == EquivalenceKind.SAME_NODE


def test_propose_alignment_finds_shared_property(tmp_path: Path, two_recordsets_croissant: Path) -> None:
    # Reuse the croissant twice; the proposer should suggest equivalences
    # between any nodes that share property names.
    a = tmp_path / "a.mapping.yaml"
    b = tmp_path / "b.mapping.yaml"
    propose_mapping(two_recordsets_croissant, write_to=a)
    propose_mapping(two_recordsets_croissant, write_to=b)

    result = propose_alignment([a, b])
    equivalences = result["alignment"]["equivalences"]
    assert len(equivalences) > 0
    assert all(eq["kind"] == EquivalenceKind.SAME_NODE.value for eq in equivalences)
