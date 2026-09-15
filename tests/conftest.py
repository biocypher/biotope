"""Shared fixtures for command-layer tests."""

from __future__ import annotations

import pytest


ANNOTATION_VALIDATION_CONFIG = {
    "annotation_validation": {
        "enabled": True,
        "minimum_required_fields": ["name", "description", "creator", "dateCreated", "distribution"],
        "field_validation": {
            "name": {"type": "string", "min_length": 1},
            "description": {"type": "string", "min_length": 10},
            "creator": {"type": "object", "required_keys": ["name"]},
            "dateCreated": {"type": "string", "format": "date"},
            "distribution": {"type": "array", "min_length": 1},
        },
    },
}


@pytest.fixture
def biotope_project(tmp_path):
    """Minimal biotope project root with git and datasets dir."""
    (tmp_path / ".git").mkdir()
    biotope_dir = tmp_path / ".biotope"
    biotope_dir.mkdir()
    (biotope_dir / "datasets").mkdir()
    (biotope_dir / "cache").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def git_repo(biotope_project):
    """Project inside a mocked git repo."""
    from unittest import mock

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        yield biotope_project
