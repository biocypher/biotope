"""Unit tests for biotope utilities."""

import yaml

from biotope.utils import load_project_metadata


def test_load_project_metadata(tmp_path):
    """Test loading project metadata from configuration."""
    # Create a mock biotope project structure
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    biotope_dir = project_dir / ".biotope"
    biotope_dir.mkdir()

    # Create config with project metadata
    config_data = {
        "version": "1.0",
        "project_metadata": {
            "description": "Test project description",
            "url": "https://example.com",
            "creator": "test@example.com",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "citation": "Please cite this dataset as: {name} ({year})",
            "project_name": "test_project",
            "access_restrictions": "Public",
            "legal_obligations": "None",
            "collaboration_partner": "Test Institute",
        },
    }

    config_file = biotope_dir / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    # Test loading project metadata
    result = load_project_metadata(project_dir)

    assert result["description"] == "Test project description"
    assert result["url"] == "https://example.com"
    assert result["creator"]["name"] == "test@example.com"
    assert result["creator"]["@type"] == "Person"
    assert result["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert result["citation"] == "Please cite this dataset as: {name} ({year})"
    assert result["cr:projectName"] == "test_project"
    assert result["cr:accessRestrictions"] == "Public"
    assert result["cr:legalObligations"] == "None"
    assert result["cr:collaborationPartner"] == "Test Institute"
