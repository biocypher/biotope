"""Shared fixtures for command-layer tests."""

from __future__ import annotations

import yaml
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
def biotope_project_with_registry(biotope_project):
    """Biotope project with MCP registry config."""
    config = {
        "version": "1.0",
        "registries": {"mcp": {"url": "https://biocontext.ai/registry.json", "cache_duration": 3600}},
        **ANNOTATION_VALIDATION_CONFIG,
    }
    config_file = biotope_project / ".biotope" / "config.yaml"
    config_file.write_text(yaml.dump(config))
    return biotope_project


@pytest.fixture
def mock_mcp_registry_data():
    return [
        {
            "name": "BioMCP",
            "identifier": "genomoncology/biomcp",
            "description": "A Model Context Protocol server for bioinformatics",
            "keywords": ["PubMed", "ClinicalTrials", "MyVariant", "python"],
            "codeRepository": "https://github.com/genomoncology/biomcp",
        },
        {
            "name": "AACT MCP",
            "identifier": "navisbio/AACT_MCP",
            "description": "Clinical trials data access",
            "keywords": ["AACT", "python"],
            "codeRepository": "https://github.com/navisbio/AACT_MCP",
        },
    ]


@pytest.fixture
def git_repo(biotope_project):
    """Project inside a mocked git repo."""
    from unittest import mock

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        yield biotope_project
