"""Tests for the annotate command surface."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest
import yaml
from click.testing import CliRunner

from biotope.commands.annotate import annotate, validate


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


@pytest.fixture
def annotated_project(tmp_path):
    project_root = tmp_path
    (project_root / ".git").mkdir()
    datasets_dir = project_root / ".biotope" / "datasets" / "data" / "inputs"
    datasets_dir.mkdir(parents=True)
    data_dir = project_root / "data" / "inputs" / "opentargets"
    data_dir.mkdir(parents=True)

    metadata_path = datasets_dir / "opentargets.jsonld"
    metadata = {
        "@context": {
            "@vocab": "https://schema.org/",
            "cr": "https://mlcommons.org/croissant/",
            "sc": "https://schema.org/",
        },
        "@type": "Dataset",
        "name": "data/inputs/opentargets",
        "description": "Open Targets dataset",
        "creator": {"@type": "Person", "name": "Open Targets"},
        "license": "CC-BY-4.0",
        "distribution": [
            {
                "@type": "cr:FileObject",
                "@id": "file_genes",
                "name": "genes.parquet",
                "contentUrl": "data/inputs/opentargets/genes.parquet",
                "encodingFormat": "application/parquet",
                "sha256": "abc123",
            },
            {
                "@type": "cr:FileObject",
                "@id": "file_diseases",
                "name": "diseases.parquet",
                "contentUrl": "data/inputs/opentargets/diseases.parquet",
                "encodingFormat": "application/parquet",
                "sha256": "def456",
            },
        ],
        "recordSet": [
            {
                "@type": "cr:RecordSet",
                "@id": "#genes",
                "name": "genes",
                "field": [
                    {
                        "@type": "cr:Field",
                        "name": "gene_id",
                        "dataType": "sc:Text",
                        "source": {
                            "fileObject": {"@id": "file_genes"},
                            "extract": {"column": "gene_id"},
                        },
                    }
                ],
            },
            {
                "@type": "cr:RecordSet",
                "@id": "#diseases",
                "name": "diseases",
                "field": [
                    {
                        "@type": "cr:Field",
                        "name": "disease_id",
                        "dataType": "sc:Text",
                        "source": {
                            "fileObject": {"@id": "file_diseases"},
                            "extract": {"column": "disease_id"},
                        },
                    }
                ],
            },
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))

    scaffold_path = data_dir / ".biotope.yaml"
    scaffold = {
        "dataset": {
            "source_path": "data/inputs/opentargets",
            "name": "Open Targets",
            "description": "OT v3",
            "creator": "Open Targets",
            "license": "CC-BY-4.0",
            "keywords": ["gene", "disease"],
        },
        "record_sets": [
            {
                "id": "#genes",
                "source_path": "data/inputs/opentargets/genes",
                "name": "genes",
                "description": "Gene table",
                "encoding_format": "application/vnd.apache.parquet",
            },
            {
                "id": "#diseases",
                "source_path": "data/inputs/opentargets/diseases",
                "name": "diseases",
                "description": "Disease table",
                "encoding_format": "application/parquet",
            },
        ],
    }
    scaffold_path.write_text(yaml.safe_dump(scaffold, sort_keys=False))

    return project_root, data_dir, scaffold_path, metadata_path


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


def test_apply_directory_updates_dataset_and_record_sets(runner, annotated_project):
    project_root, data_dir, _scaffold_path, metadata_path = annotated_project

    with runner.isolated_filesystem():
        original_cwd = Path.cwd()
        try:
            os.chdir(project_root)
            result = runner.invoke(annotate, ["apply", str(data_dir)])
        finally:
            os.chdir(original_cwd)

    assert result.exit_code == 0, result.output
    updated = json.loads(metadata_path.read_text())
    from biotope.graph.sources import protect_curated

    with pytest.raises(ValueError, match="curated"):
        protect_curated(metadata_path)
    assert updated["description"] == "OT v3"
    assert updated["keywords"] == ["gene", "disease"]
    assert updated["recordSet"][0]["description"] == "Gene table"
    assert updated["distribution"][0]["encodingFormat"] == "application/vnd.apache.parquet"


def test_apply_scaffold_with_set_override(runner, annotated_project):
    project_root, _data_dir, scaffold_path, metadata_path = annotated_project

    with runner.isolated_filesystem():
        original_cwd = Path.cwd()
        try:
            os.chdir(project_root)
            result = runner.invoke(
                annotate,
                ["apply", str(scaffold_path), "--set", "creator=Open Targets Consortium"],
            )
        finally:
            os.chdir(original_cwd)

    assert result.exit_code == 0, result.output
    updated = json.loads(metadata_path.read_text())
    assert updated["creator"]["name"] == "Open Targets Consortium"


def test_apply_rejects_unknown_record_set_id(runner, annotated_project):
    project_root, _data_dir, scaffold_path, _metadata_path = annotated_project
    scaffold = yaml.safe_load(scaffold_path.read_text())
    scaffold["record_sets"].append({"id": "#unknown", "name": "unknown", "description": "Unknown"})
    scaffold_path.write_text(yaml.safe_dump(scaffold, sort_keys=False))

    with runner.isolated_filesystem():
        original_cwd = Path.cwd()
        try:
            os.chdir(project_root)
            result = runner.invoke(annotate, ["apply", str(scaffold_path)])
        finally:
            os.chdir(original_cwd)

    assert result.exit_code != 0
    assert "Unknown record_set id" in result.output


def test_apply_rejects_scaffold_without_dataset_block(runner, annotated_project):
    project_root, _data_dir, scaffold_path, _metadata_path = annotated_project
    scaffold_path.write_text(yaml.safe_dump({"record_sets": []}, sort_keys=False))

    with runner.isolated_filesystem():
        original_cwd = Path.cwd()
        try:
            os.chdir(project_root)
            result = runner.invoke(annotate, ["apply", str(scaffold_path)])
        finally:
            os.chdir(original_cwd)

    assert result.exit_code != 0
    assert "must contain a `dataset` block" in result.output


def test_merge_record_set_row_keeps_list_encoding_format():
    """`add` writes the manifest's encodingFormat into the scaffold verbatim, so a
    compressed file puts a list in the row; apply used to raise on `.strip()`."""
    from biotope.commands.annotate import _merge_record_set_row

    metadata = {"distribution": [{"@id": "cells-fileset", "@type": "cr:FileSet", "encodingFormat": "x"}]}
    record_set = {
        "@id": "cells",
        "field": [{"source": {"fileSet": {"@id": "cells-fileset"}}}],
    }
    row = {
        "encoding_format": ["application/vnd.apache.parquet", "application/gzip"],
    }

    _merge_record_set_row(metadata, record_set, row)

    assert metadata["distribution"][0]["encodingFormat"] == [
        "application/vnd.apache.parquet",
        "application/gzip",
    ]
