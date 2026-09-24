import sys

import pytest
from synthetic import Project

from biotope.graph import build


@pytest.fixture
def project(tmp_path, monkeypatch):
    # Tests rewrite schemas within one second, and bytecode cached from the old text would hide the edit.
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    return Project(tmp_path / "project")


@pytest.fixture
def unchecked_definitions(monkeypatch):
    monkeypatch.setattr(build, "check_pipeline", lambda *args, **kwargs: {"state": "checked"})
