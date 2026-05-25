from pathlib import Path

from biotope.croissant.registry import LocalRegistryClient


def test_local_registry_reads_meta(tmp_path: Path) -> None:
    server_dir = tmp_path / "servers" / "example-adapter"
    server_dir.mkdir(parents=True)
    (server_dir / "meta.yaml").write_text(
        "identifier: biocypher/example\n"
        "name: Example\n"
        "description: An example adapter.\n"
        "croissantFile: https://example.com/croissant.json\n"
        "biocypherSchemaConfig: https://example.com/schema_config.yaml\n"
        "producedEntities: [gene, disease]\n"
        "producedRelations: [gene_associated_with_disease]\n",
    )

    client = LocalRegistryClient(tmp_path)
    metas = list(client.list_adapters())
    assert len(metas) == 1
    assert metas[0].identifier == "biocypher/example"
    assert metas[0].produced_entities == ["gene", "disease"]

    matches = list(client.find_by_entity("gene"))
    assert len(matches) == 1
