import csv
import importlib.metadata
import json
import re
import shutil
from dataclasses import fields
from pathlib import Path

from typed_example import EXAMPLE, prepare, run

import biotope
from biotope.graph import Pipeline


def rows(part):
    header = next(csv.reader([part.with_name(part.name.replace("part000", "header")).read_text()]))
    with part.open() as stream:
        return list(csv.DictReader(stream, fieldnames=header))


def test_the_example_checks_builds_records_its_dependencies_and_reports_a_failed_load(tmp_path):
    assert "dependencies" not in {member.name for member in fields(Pipeline)}
    root = prepare(tmp_path)
    shutil.rmtree(root / "raw")
    mapping = root / "graph/mappings/sample/__init__.py"
    good = mapping.read_text()
    mapping.write_text(
        good.replace("row.score", "row.renamed_score")
        .replace("row.tissue.lower()", "5")
        .replace("FromPerson(source=sample_id, target=person_id)", "FromPerson(source=person_id, target=sample_id)")
        .replace(
            "Sample(id=sample_id, tissue=measurement.value.tissue, doubled_score=measurement.value.score)",
            "Sample(id=sample_id)",
        )
    )
    result = run(root)
    assert result.returncode != 0
    errors = " ".join(result.stderr.split())
    for problem in (
        "renamed_score",
        "PersonId",
        "SampleId",
        'Arguments missing for parameters "tissue", "doubled_score"',
    ):
        assert problem in errors

    mapping.write_text(good)
    shutil.copytree(EXAMPLE / "raw", root / "raw")
    (root / "raw/people.csv").write_text('person_id,name\np1,"Ada ""A"""\np2,Bea\n')
    pyproject = root / "graph/pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace('<0.11"]', '<0.11", "rich>=13", "click>=8"]'))
    paths = root / "graph/paths.py"
    paths.write_text(
        paths.read_text() + "\nimport json\n\nimport yaml\nfrom rich.markup import escape\n\n"
        'LABEL = escape(yaml.safe_dump(json.loads("[]")))\n'
    )
    result = run(root, "build", "first")
    assert result.returncode == 0, result.stdout + result.stderr
    build = root / "graph/build/first"
    report = json.loads((build / "run.json").read_text())
    assert report["state"] == "complete" and report["schema_version"] == 2
    assert {path.name for path in build.iterdir()} == {
        "schema_config.yaml",
        "biocypher_config.yaml",
        "run.json",
        "provenance.json",
        "biocypher",
    }
    assert {p.name for p in root.iterdir()} == {"graph", "metadata", "raw", "project.yaml", ".biotope"}
    assert report["definitions"]["type_check"]["filesAnalyzed"] == len(report["definitions"]["code_digests"])
    assert report["graph_objects"] == {"nodes": 3, "edges": 2} and len(report["findings"]) == 2
    assert len(report["dependencies"]["biotope"]["source_digest"]) == 64
    for name in ("biotope", "click", "pyyaml", "rich"):
        assert report["dependencies"][name]["version"] == importlib.metadata.version(name)
    assert report["definitions"]["imports"] == {"rich": ["rich"], "yaml": ["pyyaml"]}
    [undeclared] = [f for f in report["definitions"]["findings"] if f["code"] == "dependencies.undeclared"]
    assert undeclared["subject"] == "pyyaml" and "graph/pyproject.toml" in undeclared["message"]
    samples = rows(build / "biocypher/Sample-part000.csv")
    assert [(row[":ID"], float(row["doubled_score:double"])) for row in samples] == [
        ("fixture:sample:s1", 3.0),
        ("fixture:sample:s2", 5.0),
    ]
    assert all("Sample" in row[":LABEL"].split("|") for row in samples)
    with (build / "biocypher/FromPerson-part000.csv").open() as stream:
        assert all(row[-1] == "FromPerson" for row in csv.reader(stream))
    [ada] = [row for row in rows(build / "biocypher/Person-part000.csv") if row["name"] == 'Ada "A"']
    provenance = json.loads((build / "provenance.json").read_text())
    assert len(provenance["records"][int(ada["biotope_provenance_id:long"])]["evidence"]) == 3

    assert run(root, "metagraph").returncode == 0
    viewer = (root / "graph/metagraph.html").read_text()
    assert "graph/topology/sample/node.py" in viewer and str(root) not in viewer

    raw = root / "raw/samples.csv"
    raw.write_text(raw.read_text().replace("1.5", "bad"))
    failed = run(root, "build", "invalid-values")
    assert failed.returncode != 0 and "line:2" in "".join(line.strip() for line in failed.stderr.splitlines())
    blocks = re.split(r"\n(?=\S)", failed.stderr.strip())
    assert [block.split(None, 1)[1].strip() for block in blocks if block.startswith("Phase")] == [
        "Checking definitions",
        "Checking the exporter",
        "Running project loaders and mappings",
    ]
    status, *detail = blocks[-1].splitlines()
    assert status.split() == ["FAIL", "example:sample-people"]
    assert "".join(line.strip() for line in detail).startswith("execution.failed: study/samples")
    assert json.loads((root / "graph/build/invalid-values/run.json").read_text())["state"] == "failed"


def test_the_example_graph_ignores_every_file_the_scaffold_ignores():
    scaffold = Path(biotope.__file__).parent / "templates/graph/.gitignore"
    ignored = set((EXAMPLE / "graph/.gitignore").read_text().splitlines())
    assert set(scaffold.read_text().splitlines()) <= ignored
