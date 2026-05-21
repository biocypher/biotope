"""Tests for the build/materialize path against the semantic IR."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from biotope.croissant.api import materialize
from biotope.croissant.mapping import Mapping, dump_mapping


def _write_minimal_mapping(path: Path, croissant: Path) -> None:
    mapping = Mapping.model_validate(
        {
            "croissant": str(croissant),
            "entities": {
                "gene": {
                    "record_set": "genes",
                    "id": {
                        "field": "ensembl_id",
                        "transform": "as_curie",
                        "args": {"prefix": "ensembl"},
                    },
                    "properties": {"symbol": "symbol", "biotype": "biotype"},
                }
            },
        }
    )
    dump_mapping(mapping, path)


def test_materialize_minimal(tmp_path: Path, minimal_croissant: Path) -> None:
    mapping_path = tmp_path / "minimal.mapping.yaml"
    _write_minimal_mapping(mapping_path, minimal_croissant)

    project_dir = tmp_path / "project"
    result = materialize(project_dir, [mapping_path])

    assert (project_dir / "config" / "schema_config.yaml").exists()
    biocypher_config = project_dir / "config" / "biocypher_config.yaml"
    assert biocypher_config.exists()
    bc_yaml = yaml.safe_load(biocypher_config.read_text())
    # Headless by default: no remote Biolink fetch on build.
    assert bc_yaml["biocypher"]["head_ontology"] is None
    assert (project_dir / "mappings" / "minimal.mapping.yaml").exists()
    assert (project_dir / "create_knowledge_graph.py").exists()
    assert (project_dir / "generated" / "minimal" / "adapter.py").is_file()
    assert (project_dir / "generated" / "minimal" / "__init__.py").is_file()

    schema_text = (project_dir / "config" / "schema_config.yaml").read_text()
    schema_yaml = yaml.safe_load(
        "\n".join(line for line in schema_text.splitlines() if not line.startswith("#"))
    )
    assert "gene" in schema_yaml
    gene = schema_yaml["gene"]
    assert gene["represented_as"] == "node"
    assert gene["input_label"] == "gene"
    assert gene["namespace"] == "ensembl"
    assert "preferred_id" not in gene
    assert result["project_dir"] == str(project_dir)
    assert "minimal" in result["generated_packages"]


def test_strict_build_rejects_unresolved(tmp_path: Path, minimal_croissant: Path) -> None:
    mapping_path = tmp_path / "incomplete.mapping.yaml"
    mapping_path.write_text(
        yaml.safe_dump(
            {
                "croissant": str(minimal_croissant),
                "entities": {"gene": {}},
            },
            sort_keys=False,
        )
    )
    project_dir = tmp_path / "project"
    with pytest.raises(ValueError, match="not fully resolved"):
        materialize(project_dir, [mapping_path])


def test_relation_edge_in_schema(tmp_path: Path, two_recordsets_croissant: Path) -> None:
    mapping_path = tmp_path / "two.mapping.yaml"
    mapping = Mapping.model_validate(
        {
            "croissant": str(two_recordsets_croissant),
            "entities": {
                "gene": {"record_set": "genes", "id": "gene_id"},
                "disease": {"record_set": "gene_disease", "id": "disease_id"},
            },
            "relations": {
                "gene_in_disease": {
                    "record_set": "gene_disease",
                    "source": {"entity": "gene", "field": "gene_id"},
                    "target": {"entity": "disease", "field": "disease_id"},
                    "properties": {"score": "score"},
                }
            },
        }
    )
    dump_mapping(mapping, mapping_path)

    project_dir = tmp_path / "project"
    materialize(project_dir, [mapping_path])

    schema_text = (project_dir / "config" / "schema_config.yaml").read_text()
    schema_yaml = yaml.safe_load(
        "\n".join(line for line in schema_text.splitlines() if not line.startswith("#"))
    )
    assert "gene in disease" in schema_yaml
    rel = schema_yaml["gene in disease"]
    assert rel["represented_as"] == "edge"
    assert rel["input_label"] == "gene_in_disease"
    assert rel["source"] == "gene"
    assert rel["target"] == "disease"
    assert "is_a" not in rel
