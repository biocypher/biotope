import pytest
from graph_project import buildable


@pytest.fixture
def project(tmp_path, monkeypatch):
    return buildable(tmp_path, monkeypatch)
