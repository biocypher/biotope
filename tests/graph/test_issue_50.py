"""AC-17, the decisions of #50: sameAs copies, one dependency declaration, reserved property names."""

import gzip
import importlib.metadata
import json
from dataclasses import fields

from croissant_baker.metadata_generator import MetadataGenerator
from typed_example import prepare, run

from biotope.graph import Pipeline


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


def test_run_json_records_every_declared_and_every_imported_distribution(tmp_path):
    assert "dependencies" not in {member.name for member in fields(Pipeline)}
    root = prepare(tmp_path)
    pyproject = root / "graph/pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace('<0.11"]', '<0.11", "PyYAML>=6"]'))
    paths = root / "graph/paths.py"
    paths.write_text(paths.read_text() + '\nfrom rich.markup import escape\n\nLABEL = escape("[study]")\n')
    result = run(root, "build", "recorded")
    assert result.returncode == 0, result.stdout + result.stderr
    recorded = json.loads((root / "graph/build/recorded/run.json").read_text())["dependencies"]
    for name in ("biotope", "pyyaml", "rich"):
        assert recorded[name]["version"] == importlib.metadata.version(name)
