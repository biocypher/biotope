from pathlib import Path

from biotope.croissant.api import materialize, propose_mapping


def test_materialize_minimal(tmp_path: Path, minimal_croissant: Path) -> None:
    mapping_path = tmp_path / "minimal.mapping.yaml"
    propose_mapping(minimal_croissant, write_to=mapping_path)

    project_dir = tmp_path / "project"
    result = materialize(project_dir, [mapping_path])

    assert (project_dir / "config" / "schema_config.yaml").exists()
    assert (project_dir / "config" / "biocypher_config.yaml").exists()
    assert (project_dir / "mappings" / "minimal.mapping.yaml").exists()
    assert (project_dir / "create_knowledge_graph.py").exists()

    schema_text = (project_dir / "config" / "schema_config.yaml").read_text()
    assert "represented_as: node" in schema_text
    assert result["project_dir"] == str(project_dir)
