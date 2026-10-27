import pytest
from graph_project import buildable


@pytest.fixture
def project(tmp_path, monkeypatch):
    return buildable(tmp_path, monkeypatch)


@pytest.fixture
def single(tmp_path, monkeypatch):
    return buildable(tmp_path, monkeypatch, "data/raw/people.csv")
