"""One real checker and BioCypher path, including revisions and failure reports."""

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from biotope.graph.sources import generate_source, register_metadata


EXAMPLE = Path(__file__).resolve().parents[2] / "examples/typed_graph"


def prepare(tmp_path):
    root = tmp_path / "project"
    shutil.copytree(EXAMPLE, root, ignore=shutil.ignore_patterns("__pycache__", ".biotope", "build"))
    (root / ".biotope").mkdir(exist_ok=True)
    for name in ("samples", "people"):
        manifest = register_metadata(
            root, root / f"graph/metadata/{name}.jsonld", name, reason="Reviewed synthetic fixture-v1"
        )
        generate_source(manifest, root / f"graph/sources/{name}/schema.py")
    registered = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from graph.sources import SOURCES
from graph.mappings import MAPPINGS
from graph.topology import TOPOLOGY
from graph.pipelines.build_graph import PIPELINE
assert PIPELINE.sources is SOURCES
assert PIPELINE.mappings is MAPPINGS
assert PIPELINE.topology is TOPOLOGY
""",
        ],
        cwd=root,
        text=True,
        capture_output=True,
    )
    assert registered.returncode == 0, registered.stdout + registered.stderr
    return root


def run(root, action="check", output=None):
    command = [sys.executable, "-m", "biotope.cli", "graph", action, "graph.pipelines.build_graph:PIPELINE"]
    if output:
        command += ["--out", "graph/build/" + output]
    return subprocess.run(command, cwd=root, text=True, capture_output=True)


def test_real_checker_revision_and_biocypher_build(tmp_path):
    root = prepare(tmp_path)
    # No raw files at all: Python declarations and static checks must still work.
    shutil.rmtree(root / "raw")
    result = run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    mapping = root / "graph/mappings/samples.py"
    good = mapping.read_text()
    mapping.write_text(
        good.replace("sample.score", "sample.renamed_score")
        .replace("sample.tissue.lower()", "5")
        .replace("FromPerson(source=sample_id, target=person_id)", "FromPerson(source=person_id, target=sample_id)")
    )
    result = run(root)
    assert result.returncode != 0
    assert "renamed_score" in result.stderr and "PersonId" in result.stderr and "SampleId" in result.stderr
    mapping.write_text(good)
    shutil.copytree(EXAMPLE / "raw", root / "raw")
    (root / "raw/people.csv").write_text('person_id,name\np1,"Ada ""A"""\np2,Bea\n')
    for name in ("first", "second"):
        result = run(root, "build", name)
        assert result.returncode == 0, result.stdout + result.stderr
    first, second = (json.loads((root / "graph/build" / n / "run.json").read_text()) for n in ("first", "second"))
    assert first["state"] == "complete"
    assert {p.name for p in root.iterdir()} == {"graph", "raw", "project.yaml", ".biotope"}
    assert first["definitions"]["type_check"]["filesAnalyzed"] == len(first["definitions"]["code_digests"])
    assert first["graph_digest"] == second["graph_digest"]
    assert first["graph_objects"] == {"nodes": 3, "edges": 2}
    software = first["dependencies"]["biotope"]
    assert software["version"] and len(software["source_digest"]) == 64
    assert software == second["dependencies"]["biotope"]
    assert len(first["findings"]) == 2
    provenance = [json.loads(line) for line in (root / "graph/build/first/provenance.jsonl").read_text().splitlines()]
    ada = next(item for item in provenance if item["id"] == "fixture:person:p1")
    assert len(ada["evidence"]) == 3
    csv_files = list((root / "graph/build/first/biocypher").glob("*.csv"))
    assert csv_files and any("fixture:sample:s1" in path.read_text() for path in csv_files)
    samples_file = next(path for path in csv_files if "Sample" in path.name and "part000" in path.name)
    header = next(csv.reader([samples_file.with_name(samples_file.name.replace("part000", "header")).read_text()]))
    with samples_file.open() as stream:
        rows = list(csv.DictReader(stream, fieldnames=header))
    assert [(row[":ID"], float(row["doubled_score:double"])) for row in rows] == [
        ("fixture:sample:s1", 3.0),
        ("fixture:sample:s2", 5.0),
    ]
    assert all("ExampleSample" in row[":LABEL"].split("|") for row in rows)
    edge_file = root / "graph/build/first/biocypher/ExampleFromPerson-part000.csv"
    with edge_file.open() as stream:
        assert all(row[-1] == "ExampleFromPerson" for row in csv.reader(stream))
    people_file = next(
        path for path in csv_files if "Person" in path.name and "From" not in path.name and "part000" in path.name
    )
    with people_file.open() as stream:
        assert next(csv.reader(stream))[1] == 'Ada "A"'
    raw = root / "raw/samples.csv"
    raw_text = raw.read_text()
    raw.write_text(raw_text.replace("1.5", "bad"))
    failed = run(root, "build", "invalid-values")
    assert failed.returncode != 0 and "line:2" in failed.stderr
    assert json.loads((root / "graph/build/invalid-values/run.json").read_text())["state"] == "failed"
    raw.write_text(raw_text)
    manifest = root / ".biotope/datasets/samples.jsonld"
    data = json.loads(manifest.read_text())
    data["recordSet"][0]["field"][3]["name"] = "new_score"
    manifest.write_text(json.dumps(data))
    result = run(root, "build", "failed")
    assert result.returncode != 0 and "stale" in result.stderr
    assert json.loads((root / "graph/build/failed/run.json").read_text())["state"] == "failed"
    assert not (root / "graph/build/failed/biocypher").exists()
    assert mapping.read_text() == good

    generate_source(manifest, root / "graph/sources/samples/schema.py")
    result = run(root)
    assert result.returncode != 0 and "score" in result.stderr
    loader = root / "graph/sources/samples/loader.py"
    loader.write_text(loader.read_text().replace("score=float", "new_score=float"))
    mapping.write_text(good.replace("sample.score", "sample.new_score"))
    node = root / "graph/topology/sample/node.py"
    node.write_text(node.read_text().replace("doubled_score:", "adjusted_score:"))
    result = run(root)
    assert result.returncode != 0 and "doubled_score" in result.stderr
    mapping.write_text(mapping.read_text().replace("doubled_score=", "adjusted_score="))
    result = run(root, "build", "repaired")
    assert result.returncode == 0, result.stdout + result.stderr
    repaired = json.loads((root / "graph/build/repaired/run.json").read_text())
    assert repaired["state"] == "complete"
    assert repaired["definitions"]["topology_digest"] != first["definitions"]["topology_digest"]
