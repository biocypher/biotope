from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "croissant"


@pytest.fixture
def minimal_croissant() -> Path:
    return FIXTURES / "minimal.croissant.json"


@pytest.fixture
def two_recordsets_croissant() -> Path:
    return FIXTURES / "two_recordsets.croissant.json"


@pytest.fixture
def gene_csv(tmp_path: Path) -> Path:
    p = tmp_path / "genes.csv"
    p.write_text(
        "ensembl_id,symbol,biotype\n"
        "ENSG00000139618,BRCA2,protein_coding\n"
        "ENSG00000141510,TP53,protein_coding\n"
    )
    return p


@pytest.fixture
def two_recordsets_dir(tmp_path: Path) -> Path:
    (tmp_path / "genes.csv").write_text(
        "gene_id,symbol\nG1,BRCA2\nG2,TP53\n",
    )
    (tmp_path / "gene_disease.csv").write_text(
        "association_id,gene_id,disease_id,score\nA1,G1,D1,0.9\nA2,G2,D2,0.7\n",
    )
    return tmp_path
