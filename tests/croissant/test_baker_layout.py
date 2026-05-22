"""Regression: baker-shaped Croissants (FileSet @id = <rs>-fileset; field source links).

Mirrors what `biotope add <directory>` produces via croissant-baker: each
record set in a directory has a FileSet whose @id is ``<rs.name>-fileset``,
referenced from each field's ``source.fileSet.@id``. The Croissant JSON-LD
lives under ``.biotope/datasets/<rel>.jsonld`` and ``includes`` paths are
relative to the data directory at ``<project>/<rel>/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from biotope.croissant.acquisition import AcquisitionContext, infer_datasets_location
from biotope.croissant.spec import load_from_path


def _baker_shaped_croissant(data_dir: Path) -> dict:
    """Build a baker-style Croissant for a directory containing two record sets."""
    return {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "sc:Dataset",
        "name": "ot",
        "distribution": [
            {
                "@id": "target-fileset",
                "@type": "cr:FileSet",
                "name": "target partition files",
                "includes": "target/*.parquet",
                "encodingFormat": "application/vnd.apache.parquet",
            },
            {
                "@id": "drug_mechanism_of_action-fileset",
                "@type": "cr:FileSet",
                "name": "drug_mechanism_of_action partition files",
                "includes": "drug_mechanism_of_action/*.parquet",
                "encodingFormat": "application/vnd.apache.parquet",
            },
        ],
        "recordSet": [
            {
                "@id": "target",
                "name": "target",
                "field": [
                    {
                        "name": "id",
                        "dataType": "sc:Text",
                        "source": {
                            "fileSet": {"@id": "target-fileset"},
                            "extract": {"column": "id"},
                        },
                    },
                ],
            },
            {
                "@id": "drug_mechanism_of_action",
                "name": "drug_mechanism_of_action",
                "field": [
                    {
                        "name": "actionType",
                        "dataType": "sc:Text",
                        "source": {
                            "fileSet": {"@id": "drug_mechanism_of_action-fileset"},
                            "extract": {"column": "actionType"},
                        },
                    },
                ],
            },
        ],
    }


@pytest.fixture
def baker_project(tmp_path: Path) -> tuple[Path, Path]:
    """Recreate a baker-shaped project layout.

    Returns: (project_root, croissant_path).
    """
    project = tmp_path / "proj"
    (project / ".biotope" / "datasets" / "data" / "inputs").mkdir(parents=True)
    croissant = project / ".biotope" / "datasets" / "data" / "inputs" / "ot.jsonld"
    data_dir = project / "data" / "inputs" / "ot"

    # Write a couple of tiny CSV files masquerading as parquet for the path
    # resolution test (we only assert the resolved glob path, not actual reads).
    (data_dir / "target").mkdir(parents=True)
    (data_dir / "drug_mechanism_of_action").mkdir(parents=True)
    (data_dir / "target" / "part-0.parquet").write_bytes(b"")
    (data_dir / "drug_mechanism_of_action" / "part-0.parquet").write_bytes(b"")

    croissant.write_text(json.dumps(_baker_shaped_croissant(data_dir)))
    return project, croissant


def test_infer_datasets_location_returns_data_dir(baker_project: tuple[Path, Path], monkeypatch) -> None:
    project, croissant = baker_project
    monkeypatch.chdir(project)
    inferred = infer_datasets_location(croissant)
    assert inferred == project / "data" / "inputs" / "ot"


def test_acquisition_resolves_fileset_via_field_source(baker_project: tuple[Path, Path]) -> None:
    project, croissant = baker_project
    dataset = load_from_path(croissant)
    data_dir = project / "data" / "inputs" / "ot"

    with AcquisitionContext(dataset, datasets_location=data_dir) as ctx:
        target_path = ctx._resolve_path(dataset.record_set_by_name("target"))
        moa_path = ctx._resolve_path(dataset.record_set_by_name("drug_mechanism_of_action"))

    # Must point inside the actual data dir, not the project root.
    assert target_path == data_dir / "target" / "*.parquet"
    assert moa_path == data_dir / "drug_mechanism_of_action" / "*.parquet"


def test_acquisition_falls_back_to_id_minus_fileset_when_field_source_missing(
    tmp_path: Path,
) -> None:
    """Even without `source` on fields, the `<rs>-fileset` id convention must work."""
    data_dir = tmp_path / "data"
    (data_dir / "target").mkdir(parents=True)
    croissant_dict = {
        "@type": "sc:Dataset",
        "name": "x",
        "distribution": [
            {
                "@id": "target-fileset",
                "@type": "cr:FileSet",
                "includes": "target/*.parquet",
            }
        ],
        "recordSet": [{"@id": "target", "name": "target", "field": [{"name": "id", "dataType": "sc:Text"}]}],
    }
    cpath = tmp_path / "ot.jsonld"
    cpath.write_text(json.dumps(croissant_dict))

    dataset = load_from_path(cpath)
    with AcquisitionContext(dataset, datasets_location=data_dir) as ctx:
        path = ctx._resolve_path(dataset.record_set_by_name("target"))
    assert path == data_dir / "target" / "*.parquet"
