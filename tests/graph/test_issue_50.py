"""AC-17, the decisions of #50: sameAs copies, one dependency declaration, reserved property names."""

import gzip
import json

from croissant_baker.metadata_generator import MetadataGenerator


def test_a_compressed_copy_that_baker_links_with_same_as_makes_no_separate_source(project):
    folder = project.root / "data/table"
    folder.mkdir(parents=True)
    (folder / "table.csv").write_text("id,name\n1,a\n2,b\n")
    (folder / "table.csv.gz").write_bytes(gzip.compress((folder / "table.csv").read_bytes()))
    baked = MetadataGenerator(dataset_path=str(folder), name="table").generate_metadata()
    assert [item["name"] for item in baked["distribution"] if "sameAs" in item] == ["table.csv.gz"]
    manifest = project.root / ".biotope/datasets/table.jsonld"
    manifest.write_text(json.dumps(baked))
    result = project.run("source", "generate", str(manifest), "--out", "graph/sources")
    assert result.exit_code == 0, result.output
    packages = [path.name for path in (project.sources / "table").iterdir() if path.is_dir()]
    assert packages == ["table"]
