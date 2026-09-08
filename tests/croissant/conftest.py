from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent.parent / "fixtures" / "croissant"


@pytest.fixture
def minimal_croissant() -> Path:
    return FIXTURES / "minimal.croissant.json"


@pytest.fixture
def two_recordsets_croissant() -> Path:
    return FIXTURES / "two_recordsets.croissant.json"
