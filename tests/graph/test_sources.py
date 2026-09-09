"""Curated metadata and declaration regeneration, without source payloads."""

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from biotope.graph.sources import check_generated, generate_source, register_metadata


def import_generated(path):
    spec = importlib.util.spec_from_file_location("generated_contract_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_curated_generation_and_revision(tmp_path):
    manifest = tmp_path / "curated.jsonld"
    data = {
        "name": "source",
        "distribution": [{"@id": "absent", "@type": "cr:FileObject", "contentUrl": "absent.csv"}],
        "recordSet": [
            {
                "@id": "samples",
                "name": "sample rows",
                "field": [
                    {
                        "@id": "samples/class",
                        "name": "class",
                        "dataType": "sc:Text",
                        "description": "Reviewed annotation belongs only in Croissant.",
                        "source": {"fileObject": {"@id": "absent"}, "extract": {"column": "Original class label"}},
                        "custom:review": {"evidence": "Curator's original evidence"},
                    },
                    {"@id": "samples/a", "name": "a-b", "dataType": "sc:Integer", "biotope:nullable": False},
                    {"@id": "samples/b", "name": "a b", "dataType": "sc:Float"},
                    {
                        "name": "UnknownValueDetails",
                        "repeated": True,
                        "subField": {"name": "label", "dataType": "sc:Text"},
                    },
                    {"name": "matrix", "dataType": "cr:Float32", "cr:arrayShape": "100,200"},
                    {"name": "field", "dataType": "sc:Text"},
                    {"name": "unknown", "dataType": "custom:Unresolved"},
                ],
            }
        ],
    }
    manifest.write_text(json.dumps(data))
    root = tmp_path / "project"
    (root / ".biotope").mkdir(parents=True)
    target = register_metadata(root, manifest, "samples", reason="Reviewed source structure; matrix grain unresolved")
    generated = root / "sources/samples/schema.py"
    generate_source(target, generated)
    first = generated.read_bytes()
    # Types remain importable without reading or embedding the authoritative manifest.
    effective_text = target.read_text()
    target.unlink()
    module = import_generated(generated)
    target.write_text(effective_text)
    for metadata_only in (
        "Reviewed annotation belongs only in Croissant.",
        "Original class label",
        "Curator's original evidence",
    ):
        assert metadata_only not in generated.read_text()
        assert metadata_only in target.read_text()
    row = module.SampleRows
    assert module.RECORDS == (row,)  # Nested field classes are not independently loaded record sets.
    attrs = {f.name: f for f in dataclasses.fields(row)}
    assert len(attrs) == 7
    assert "class_" in attrs and "a_b" in attrs and "a_b_2" in attrs
    assert row.__field_refs__["class_"] == "samples/class"
    assert row.__field_refs__["a_b"] == "samples/a"
    assert row.__field_refs__["a_b_2"] == "samples/b"
    assert row.__field_refs__["UnknownValueDetails"] == "/recordSet/0/field/3"
    assert module.SampleRowsUnknownValueDetails.__field_refs__["label"] == "/recordSet/0/field/3/subField"
    assert all(not member.metadata for member in attrs.values())
    assert "list[" in row.__annotations__["UnknownValueDetails"]
    assert "UnknownValue" in row.__annotations__["matrix"]
    assert "UnknownValue" in row.__annotations__["unknown"]
    assert "None" in row.__annotations__["class_"]
    assert "None" not in row.__annotations__["a_b"]
    from biotope.graph import Pipeline, SourceContract, Topology
    from biotope.graph.check import check_pipeline

    pipeline = Pipeline(
        "fields",
        Topology((), ()),
        (SourceContract("rows", target, generated, (row,)),),
        (),
        lambda ctx: None,
        scope="metadata warnings",
        code_paths=(generated, Path(__file__)),
    )
    report = check_pipeline(pipeline, static=False)
    assert sum("opaque source contract" in warning for warning in report["warnings"]) == 2

    authored = generated.with_name("loader.py")
    authored.write_text("# project-owned loader\n")
    generate_source(target, generated)
    assert generated.read_bytes() == first
    target.write_text(json.dumps(json.loads(target.read_text()), sort_keys=True))
    generate_source(target, generated)
    assert generated.read_bytes() == first
    check_generated(target, generated)
    effective = json.loads(target.read_text())
    effective["biotope:curation"]["reason"] = "Reviewed again"
    effective["distribution"][0].update(sha256="new-payload-version", dateModified="2026-09-09")
    target.write_text(json.dumps(effective))
    check_generated(target, generated)
    assert generate_source(target, generated).read_bytes() == first
    revised_report = check_pipeline(pipeline, static=False)
    assert revised_report["sources"]["rows"]["digest"] != report["sources"]["rows"]["digest"]
    assert revised_report["sources"]["rows"]["contract_digest"] == report["sources"]["rows"]["contract_digest"]
    effective = json.loads(target.read_text())
    effective["recordSet"][0]["field"][0]["dataType"] = "sc:Integer"
    target.write_text(json.dumps(effective))
    with pytest.raises(ValueError, match="stale"):
        check_generated(target, generated)
    generate_source(target, generated)
    assert generated.read_bytes() != first
    assert authored.read_text() == "# project-owned loader\n"
    with pytest.raises(ValueError, match="already exists"):
        register_metadata(root, manifest, "samples", reason="do not clobber")


def test_rebake_stops_before_overwriting_curated_metadata(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from biotope.cli import cli

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", ".", "--no-git", "--no-prompt"]).exit_code == 0
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.csv").write_text("id\n1\n")
    authored = tmp_path / "authored.jsonld"
    authored.write_text(json.dumps({"name": "raw", "recordSet": []}))
    target = register_metadata(tmp_path, authored, "raw", reason="Unresolved; preserve review")
    before = target.read_bytes()
    result = runner.invoke(cli, ["add", "raw", "--rebake"])
    assert result.exit_code != 0
    assert "curated" in result.output.lower()
    assert target.read_bytes() == before
    (raw / "b.csv").write_text("new_field\nvalue\n")
    fresh = tmp_path / "review/raw.jsonld"
    result = runner.invoke(cli, ["add", "raw", "--bake-to", str(fresh)])
    assert result.exit_code == 0, result.output
    assert target.read_bytes() == before
    assert not (raw / ".biotope.yaml").exists()
    assert len(json.loads(fresh.read_text())["recordSet"]) == 2
    reviewed = json.loads(fresh.read_text())
    reviewed["description"] = "Reconciled with authored corrections"
    fresh.write_text(json.dumps(reviewed))
    result = runner.invoke(
        cli, ["source", "register", str(fresh), "--name", "raw", "--reason", "Reconciled", "--replace"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text())["description"] == reviewed["description"]
    # A review bake must not overwrite authored files, managed metadata, or payloads.
    for destination in (fresh, target, raw / "new.jsonld"):
        result = runner.invoke(cli, ["add", "raw", "--bake-to", str(destination)])
        assert result.exit_code != 0


def test_large_generated_contract_and_opaque_type_checks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from biotope.graph import Pipeline, Topology
    from biotope.graph.check import check_types

    data = {
        "recordSet": [
            {
                "name": f"table_{i}",
                "field": [
                    {
                        "name": f"column_{j}",
                        "dataType": "sc:Text",
                        "description": "The word UnknownValue in prose is not a type annotation.",
                        "source": {"fileObject": {"@id": f"file_{i}"}, "extract": {"column": f"column_{j}"}},
                    }
                    for j in range(200)
                ],
            }
            for i in range(55)
        ]
    }
    manifest = tmp_path / "large.jsonld"
    manifest.write_text(json.dumps(data))
    generated = generate_source(manifest, tmp_path / "schema.py")
    pipeline = Pipeline(
        "large",
        Topology((), ()),
        (),
        (),
        lambda ctx: None,
        scope="static generation regression",
        code_paths=(generated,),
    )
    assert check_types(pipeline)["errorCount"] == 0
    module = import_generated(generated)
    assert tuple(cls.__name__ for cls in module.RECORDS) == tuple(f"Table{i}" for i in range(55))
    assert module.Table54.__field_refs__["column_199"] == "/recordSet/54/field/199"

    # Opaque values remain a real type error when a mapping treats them as strings.
    manifest.write_text(
        json.dumps({"recordSet": [{"name": "opaque", "field": [{"name": "image", "dataType": "custom:Image"}]}]})
    )
    generate_source(manifest, generated)
    probe = tmp_path / "mapping.py"
    probe.write_text("from schema import Opaque\n\ndef label(row: Opaque) -> str:\n    return row.image\n")
    pipeline = dataclasses.replace(pipeline, code_paths=(generated, probe))
    with pytest.raises(ValueError, match="UnknownValue"):
        check_types(pipeline)


def test_atomic_artifacts_respect_creation_and_existing_permissions(tmp_path):
    from biotope.graph.sources import write_text_atomic

    ordinary, artifact = tmp_path / "ordinary", tmp_path / "artifact"
    ordinary.write_text("ordinary")
    write_text_atomic(artifact, "new")
    assert artifact.stat().st_mode & 0o777 == ordinary.stat().st_mode & 0o777
    artifact.chmod(0o640)
    write_text_atomic(artifact, "replacement")
    assert artifact.stat().st_mode & 0o777 == 0o640
    assert artifact.read_text() == "replacement"


def test_replacement_reports_lost_annotations_and_nested_field_ids(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from biotope.cli import cli

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".biotope").mkdir()
    reviewed = tmp_path / "reviewed.jsonld"
    reviewed.write_text(
        json.dumps(
            {
                "name": "study",
                "citation": "Reviewed citation 2026",
                "biotope:curation": {"annotation_review": "Citation and fields reviewed"},
                "recordSet": [
                    {
                        "@id": "rows",
                        "field": {
                            "@id": "rows/details",
                            "subField": [
                                {"@id": "rows/details/kept", "dataType": "sc:Text"},
                                {"@id": "rows/details/removed", "dataType": "sc:Text"},
                            ],
                        },
                    },
                    {"@id": "removed-table", "field": [{"@id": "removed-table/id"}]},
                ],
            }
        )
    )
    target = register_metadata(tmp_path, reviewed, "study", reason="Reviewed")
    assert json.loads(target.read_text())["biotope:curation"]["annotation_review"]
    replacement = json.loads(reviewed.read_text())
    del replacement["citation"], replacement["biotope:curation"]
    replacement["recordSet"].pop()
    replacement["recordSet"][0]["field"]["subField"].pop()
    reviewed.write_text(json.dumps(replacement))
    args = ["source", "register", str(reviewed), "--name", "study", "--reason", "Kept everything", "--replace"]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    for lost in ("citation", "annotation_review", "removed-table", "removed-table/id", "rows/details/removed"):
        assert lost in result.output
    assert "rows/details/kept" not in result.output
    assert "citation" not in json.loads(target.read_text())  # --replace still replaces; no implicit merge.
    again = CliRunner().invoke(cli, args)
    assert again.exit_code == 0 and "drops" not in again.output
