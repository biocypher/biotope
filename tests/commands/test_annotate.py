"""Tests for the annotate command surface."""

from __future__ import annotations

import json
import subprocess
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.annotate import validate


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_metadata_file(tmp_path):
    metadata_path = tmp_path / "metadata.json"
    metadata = {
        "@context": {
            "@vocab": "https://schema.org/",
            "cr": "https://mlcommons.org/croissant/",
            "sc": "https://schema.org/",
        },
        "@type": "Dataset",
        "name": "Gene Expression Dataset",
        "description": "RNA-seq data from cancer patients",
        "url": "https://example.com/gene_data",
        "creator": {
            "@type": "Person",
            "name": "researcher@university.edu",
        },
        "dateCreated": "2025-08-27T13:37:12.651208+00:00",
        "distribution": [
            {
                "@type": "cr:FileObject",
                "@id": "expression_data",
                "name": "expression_data.csv",
                "contentUrl": "data/expression_data.csv",
                "encodingFormat": "text/csv",
                "sha256": "0b033707ea49365a5ffdd14615825511",
            },
        ],
        "recordSet": [
            {
                "@type": "cr:RecordSet",
                "@id": "#samples",
                "name": "samples",
                "description": "Patient samples with gene expression data",
                "field": [
                    {
                        "@type": "cr:Field",
                        "@id": "#samples/patient_id",
                        "name": "patient_id",
                        "dataType": "sc:Text",
                        "source": {
                            "fileObject": {"@id": "expression_data"},
                            "extract": {"column": "patient_id"},
                        },
                    }
                ],
            }
        ],
    }
    metadata_path.write_text(json.dumps(metadata))
    return metadata_path


@mock.patch("subprocess.run")
def test_validate_command_success(mock_run, runner, sample_metadata_file):
    mock_process = mock.Mock()
    mock_process.stdout = "Done"
    mock_process.stderr = ""
    mock_run.return_value = mock_process

    result = runner.invoke(validate, ["--jsonld", str(sample_metadata_file)])

    assert result.exit_code == 0
    assert "Validation successful!" in result.output


@mock.patch("subprocess.run")
def test_validate_command_failure(mock_run, runner, sample_metadata_file):
    mock_run.side_effect = subprocess.CalledProcessError(
        1,
        ["mlcroissant", "validate"],
        stderr="Invalid schema: missing required field",
    )

    result = runner.invoke(validate, ["--jsonld", str(sample_metadata_file)])
    assert result.exit_code == 1
    assert "Validation failed" in result.output
