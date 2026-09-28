"""One real checker and BioCypher path, including revisions, drift and failure reports."""

import csv
import json
import re
import shutil

from typed_example import EXAMPLE, prepare, run


def test_real_checker_revision_and_biocypher_build(tmp_path):
    root = prepare(tmp_path)
    shutil.rmtree(root / "raw")
    result = run(root)
    assert result.returncode == 0, result.stdout + result.stderr
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
    for name in ("first", "second"):
        result = run(root, "build", name)
        assert result.returncode == 0, result.stdout + result.stderr
    first, second = (json.loads((root / "graph/build" / n / "run.json").read_text()) for n in ("first", "second"))
    assert first["state"] == "complete" and first["schema_version"] == 2
    assert {path.name for path in (root / "graph/build/first").iterdir()} == {
        "schema_config.yaml",
        "biocypher_config.yaml",
        "run.json",
        "provenance.json",
        "biocypher",
    }
    assert {p.name for p in root.iterdir()} == {"graph", "metadata", "raw", "project.yaml", ".biotope"}
    assert first["definitions"]["type_check"]["filesAnalyzed"] == len(first["definitions"]["code_digests"])
    assert first["graph_digest"] == second["graph_digest"]
    assert first["graph_objects"] == {"nodes": 3, "edges": 2}
    software = first["dependencies"]["biotope"]
    assert software["version"] and len(software["source_digest"]) == 64
    assert software == second["dependencies"]["biotope"]
    assert len(first["findings"]) == 2
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
    assert all("Sample" in row[":LABEL"].split("|") for row in rows)
    edge_file = root / "graph/build/first/biocypher/FromPerson-part000.csv"
    with edge_file.open() as stream:
        assert all(row[-1] == "FromPerson" for row in csv.reader(stream))
    people_file = next(
        path for path in csv_files if "Person" in path.name and "From" not in path.name and "part000" in path.name
    )
    people_header = next(csv.reader([people_file.with_name(people_file.name.replace("part000", "header")).read_text()]))
    with people_file.open() as stream:
        person = next(csv.DictReader(stream, fieldnames=people_header))
    assert person["name"] == 'Ada "A"'
    provenance = json.loads((root / "graph/build/first/provenance.json").read_text())
    ada = provenance["records"][int(person["biotope_provenance_id:long"])]
    assert len(ada["evidence"]) == 3
    assert run(root, "metagraph").returncode == 0
    viewer = (root / "graph/metagraph.html").read_text()
    assert "graph/topology/sample/node.py" in viewer and str(root) not in viewer
    raw = root / "raw/samples.csv"
    raw_text = raw.read_text()
    raw.write_text(raw_text.replace("1.5", "bad"))
    failed = run(root, "build", "invalid-values")
    assert failed.returncode != 0 and "line:2" in "".join(line.strip() for line in failed.stderr.splitlines())
    rows = re.split(r"\n(?=\S)", failed.stderr.strip())
    assert [row.split(None, 1)[1].strip() for row in rows if row.startswith("Phase")] == [
        "Checking definitions",
        "Checking the exporter",
        "Running project loaders and mappings",
    ]
    status, *detail = rows[-1].splitlines()
    assert status.split() == ["FAIL", "example:sample-people"]
    assert "".join(line.strip() for line in detail).startswith("execution.failed: study/samples")
    assert json.loads((root / "graph/build/invalid-values/run.json").read_text())["state"] == "failed"
    raw.write_text(raw_text)
    manifest = root / ".biotope/datasets/study.jsonld"
    reviewed = manifest.read_text()
    data = json.loads(reviewed)
    [samples] = [record for record in data["recordSet"] if record["@id"] == "samples"]
    [score] = [field for field in samples["field"] if field["@id"] == "samples/score"]
    score["dataType"] = "sc:Integer"
    manifest.write_text(json.dumps(data))
    result = run(root, "build", "failed")
    assert result.returncode != 0
    report = json.loads((root / "graph/build/failed/run.json").read_text())
    assert report["state"] == "failed"
    assert not (root / "graph/build/failed/biocypher").exists()
    [drift] = [finding for finding in report["definitions"]["findings"] if finding["code"] == "source.drift"]
    assert drift["subject"] == "study/samples"
    assert 'field samples/score: dataType "sc:Float" -> "sc:Integer"' in drift["message"]
    assert "/recordSet/0/field/3/dataType" in drift["message"]
    manifest.write_text(reviewed)
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
