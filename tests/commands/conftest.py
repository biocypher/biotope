import shutil

import pytest
from graph_project import buildable, isolate


@pytest.fixture(scope="session")
def built_projects(tmp_path_factory):
    projects = {}

    def template(people):
        if people not in projects:
            with pytest.MonkeyPatch.context() as patch:
                projects[people] = buildable(tmp_path_factory.mktemp("template"), patch, people)
        return projects[people]

    return template


def copied(template, tmp_path, monkeypatch):
    isolate(tmp_path, monkeypatch)
    root = tmp_path / "project"
    shutil.copytree(template, root, symlinks=True)
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def project(tmp_path, monkeypatch, built_projects):
    return copied(built_projects("data/study/push/people.csv"), tmp_path, monkeypatch)


@pytest.fixture
def single(tmp_path, monkeypatch, built_projects):
    return copied(built_projects("data/raw/people.csv"), tmp_path, monkeypatch)
