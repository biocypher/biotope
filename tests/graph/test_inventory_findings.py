"""`graph check` inventory findings: selection, placeholders, orphans, manifests, registrations and unscoped fields."""

import json
import shutil
from dataclasses import replace

import pytest
from synthetic import Project, file_object, record_set, states

from biotope.graph.check import check_pipeline
from biotope.graph.reports import CheckFailed
from biotope.graph.workspace import select_workspace


def test_selected_placeholders_fail_the_check_until_implemented_or_excluded(project):
    manifest = project.study(record_set("rows", "x"), files=[file_object("notes", "notes.txt", fmt="text/plain")])
    project.generate(manifest)
    assert project.codes("error")["inventory.placeholder"] == ["study/notes_txt", "study/rows"]
    project.mark_implemented("study/rows")
    project.exclude({"study/notes_txt": "Not needed for this purpose"})
    assert project.codes("error") == {}


def test_a_removed_source_is_an_orphan_until_its_directory_is_deleted(project):
    manifest = project.implemented_study(record_set("kept", "x"), record_set("gone", "y"))
    assert project.codes("error") == {}
    loader = project.sources / "study/gone/loader.py"
    authored = loader.read_bytes()
    project.edit(manifest, lambda data: data["recordSet"].pop())
    assert states(project.generate(manifest)) == {"kept": "current", "gone": "orphaned"}
    assert loader.read_bytes() == authored
    assert project.codes("error")["inventory.orphan"] == ["study/gone"]
    project.exclude({"study/gone": "Removed from the curated manifest"})
    assert "inventory.orphan" not in project.codes("error")
    assert project.codes("warning")["inventory.orphan"] == ["study/gone"]
    shutil.rmtree(project.sources / "study/gone")
    assert project.codes("error") == {"inventory.unknown_exclusion": ["study/gone"]}
    project.exclude({})
    assert project.codes("error") == {}


def test_a_removed_invalid_or_ungenerated_manifest_is_reported(project):
    manifest = project.implemented_study(record_set("rows", "x"), record_set("other", "y"))
    project.manifest("pending", [record_set("later", "z")], [file_object("data", "d")])
    assert project.codes("warning")["inventory.manifest_not_generated"] == ["pending.jsonld"]
    manifest.write_text("{not json")
    errors = project.codes("error")
    assert errors["inventory.manifest_invalid"] == ["study"] and "inventory.mismatch" not in errors
    manifest.unlink()
    found = project.codes()
    assert found["inventory.manifest_missing"] == ["study"]
    assert found["inventory.orphan"] == ["study/other", "study/rows"]


def test_a_malformed_field_invalidates_its_manifest_whether_or_not_its_package_exists(project):
    manifest = project.study(record_set("rows", "x"))
    project.generate(manifest)
    for index in (0, 1):
        if index:
            project.edit(manifest, lambda data: data["recordSet"].append(record_set("later", "y")))
        project.edit(manifest, lambda data: data["recordSet"][index]["field"][0].update({"biotope:nullable": "yes"}))
        [message] = project.messages("inventory.manifest_invalid")
        assert "biotope:nullable must be true or false" in message


def test_an_unscoped_field_fails_a_selected_schema_unless_it_binds_through_field_refs(project):
    unscoped = {"@id": "u", "field": [{"@id": "elsewhere/z", "name": "z", "dataType": "sc:Text"}]}
    project.generate(project.manifest("study", [unscoped]))
    schema = project.sources / "study/u/schema.py"
    assert 'Unscoped field @id "elsewhere/z"' in schema.read_text() and "source_field(None" in schema.read_text()
    project.mark_implemented("study/u")
    assert project.codes("error") == {"source.unscoped_field": ["study/u"], "source.contract": ["study/u"]}
    project.exclude({"study/u": "Rescoped in the next manifest revision"})
    assert "source.unscoped_field" not in project.codes()
    project.exclude({})
    field_refs = '    __field_refs__: ClassVar[dict[str, str]] = {"z": "elsewhere/z"}\n'
    text = schema.read_text().replace("source_field(None, default=None)", "None")
    schema.write_text(text.replace("    __missing_values__", field_refs + "    __missing_values__"))
    assert project.codes("error") == {}


def test_excluded_sources_are_not_validated_and_their_drift_only_warns(project):
    manifest = project.implemented_study(record_set("rows", "a", "b"), record_set("kept", "k"))
    schema = project.sources / "study/rows/schema.py"
    schema.write_text(schema.read_text().replace("    a: str | None = None", "    zzz: str | None = None"))
    assert project.codes("error")["source.contract"] == ["study/rows"]
    project.exclude({"study/rows": "Out of scope"})
    assert not project.codes("error")
    project.edit(manifest, lambda data: data["recordSet"][0]["field"][1].update(dataType="sc:Integer"))
    assert project.codes("warning")["source.drift"] == ["study/rows"] and not project.codes("error")


def select_a_copy_of_the_manifest(pipeline):
    first, second = pipeline.sources
    return first, replace(second, metadata=first.metadata.with_name("copy.jsonld"))


def test_every_disagreement_between_the_pipeline_and_the_discovered_packages_is_reported(project):
    project.implemented_study(record_set("a", "x"), record_set("b", "y"))
    for changes, subject, message in (
        (
            {"source_inventory": lambda pipeline: pipeline.source_inventory[:1], "sources": ()},
            "study/b",
            "a discovered source package is missing from source_inventory",
        ),
        (
            {"sources": select_a_copy_of_the_manifest},
            "study/b",
            "the selected contract differs from its inventory entry",
        ),
        (
            {"source_inventory": lambda pipeline: (*pipeline.source_inventory, pipeline.source_inventory[0])},
            "study/a",
            "2 inventoried sources share the name 'study/a'",
        ),
    ):
        [mismatch] = [finding for finding in project.findings(**changes) if finding["code"] == "inventory.mismatch"]
        assert mismatch["subject"] == subject and message in mismatch["message"]
    assert "inventory.absent" in project.codes("error", sources=(), source_inventory=())


def test_an_excluded_alias_never_downgrades_a_selected_schemas_drift(project):
    manifest = project.implemented_study(record_set("rows", "x"))
    project.edit(manifest, lambda data: data["recordSet"][0]["field"][0].update(dataType="sc:Integer"))
    with select_workspace(project.graph) as workspace:
        pipeline = workspace.pipeline()
        [source] = pipeline.sources
        alias = replace(source, name="alias")
        for inventory in ((source, alias), (alias, source)):
            aliased = replace(pipeline, source_inventory=inventory, excluded_sources={"alias": "unused"})
            with pytest.raises(CheckFailed) as failure:
                check_pipeline(aliased, workspace=workspace, static=False)
            found = {(f["code"], f["severity"], f["message"]) for f in failure.value.report["findings"]}
            assert ("inventory.mismatch", "error", "one schema is registered as 'alias', 'study/rows'") in found
            assert ("source.drift", "error") in {(code, severity) for code, severity, _ in found}


def test_a_registration_bound_to_another_manifest_copy_is_still_checked(project):
    manifest = project.implemented_study(record_set("rows", "x"))
    data = json.loads(manifest.read_text())
    data["recordSet"][0]["field"][0]["dataType"] = "sc:Integer"
    (project.root / "copy.jsonld").write_text(json.dumps(data))
    registration = project.sources / "study/rows/__init__.py"
    registration.write_text(
        registration.read_text().replace('"../../../../.biotope/datasets/study.jsonld"', '"../../../../copy.jsonld"')
    )
    assert project.codes("error")["source.contract"] == ["study/rows"]


def test_a_source_field_type_execution_cannot_validate_fails_the_check(project):
    project.implemented_study(record_set("rows", "x"))
    schema = project.sources / "study/rows/schema.py"
    schema.write_text(schema.read_text().replace("x: str | None = None", "x: dict[str, str] | None = None"))
    [message] = project.messages("source.contract")
    assert message.startswith("Rows.x: dict[str, str] | None cannot be validated when the source loads")


def contest_an_identity(project):
    shutil.copytree(project.sources / "study/other", project.sources / "study/other_copy")


def lose_a_loader(project):
    (project.sources / "study/rows/loader.py").unlink()


@pytest.mark.parametrize(
    ("disruption", "reported"),
    [
        pytest.param(contest_an_identity, {"inventory.conflict": ["study/other", "study/other_copy"]}, id="conflict"),
        pytest.param(Project.author_inventory, {"inventory.conflict": ["study"]}, id="authored-inventory"),
        pytest.param(lose_a_loader, {"inventory.stale": ["study/rows", "study/later"]}, id="incomplete-package"),
    ],
)
def test_a_broken_package_or_root_hides_none_of_the_roots_other_findings(project, disruption, reported):
    manifest = project.implemented_study(record_set("rows", "x"), record_set("other", "y"), record_set("gone", "z"))

    def change(data):
        data["recordSet"].pop()
        data["recordSet"].append(record_set("later", "w"))
        data["recordSet"][0]["field"][0]["dataType"] = "sc:Integer"

    project.edit(manifest, change)
    disruption(project)
    found = project.codes("error")
    assert found["source.drift"] == ["study/rows"] and "study/rows" not in found.get("source.contract", [])
    assert found["inventory.orphan"] == ["study/gone"] and "study/later" in found["inventory.stale"]
    assert {code: sorted(found[code]) for code in reported} == {code: sorted(value) for code, value in reported.items()}


@pytest.mark.parametrize("operation", ["check", "build", "quality"])
def test_inventory_findings_survive_a_pipeline_that_cannot_be_imported(project, operation):
    manifest = project.study(record_set("rows", "x"))
    project.generate(manifest)
    project.edit(manifest, lambda data: data["recordSet"].append(record_set("later", "y")))
    (project.graph / "mappings/__init__.py").write_text("raise RuntimeError('broken project code')\n")
    result = project.run("graph", operation, "--json")
    codes = [finding["code"] for finding in json.loads(result.stdout)["findings"]]
    assert result.exit_code != 0 and codes == ["inventory.stale", "workspace.load"]
