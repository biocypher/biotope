import json

from synthetic import file_object, record_set, states

from biotope.graph.inventory import plan_sources


def test_drift_shows_the_current_contract_and_is_acknowledged_by_updating_the_digest(project):
    manifest = project.implemented_study(record_set("x", "f", "g"), record_set("y", "h"))
    project.edit(manifest, lambda data: data["recordSet"][0]["field"][1].update(dataType="sc:Float"))
    [drift] = [finding for finding in project.findings() if finding["code"] == "source.drift"]
    assert (drift["subject"], drift["severity"]) == ("study/x", "error")
    assert "x/g: sc:Float" in drift["message"]
    project.acknowledge_drift(manifest)
    assert project.codes("error") == {}


def test_edits_outside_the_contract_change_no_revision(project):
    paper = file_object("paper", "p.pdf", fmt="application/pdf")
    manifest = project.implemented_study(record_set("rows", "a", "b"), files=[paper])
    reviewed = project.snapshot()
    before = project.report()["sources"]["study/rows"]

    def describe(data):
        data["description"] = "A synthetic study."
        data["biotope:curation"] = {"reason": "Reviewed again"}
        data["@context"].update(biotope="https://biocypher.org/biotope/", dct="http://purl.org/dc/terms/")
        rows = data["recordSet"][0]
        rows.update(name="Rows", description="One row per sample.")
        rows["field"][0].update(
            name="Sample", description="The sample.", equivalentProperty="https://schema.org/identifier"
        )
        for resource in data["distribution"]:
            resource.update(
                sha256="1" * 64,
                md5="2" * 32,
                contentSize="3 MB",
                dateModified="2026-09-09",
                description="Downloaded again.",
            )

    project.edit(manifest, describe)
    manifest.write_text(json.dumps(json.loads(manifest.read_text()), sort_keys=True))
    assert project.codes("error") == {}
    after = project.report()["sources"]["study/rows"]
    assert after["digest"] != before["digest"] and after["contract_digest"] == before["contract_digest"]
    assert states(project.generate(manifest)) == {"rows": "current", "p_pdf": "current"}
    assert project.snapshot() == reviewed
    project.edit(manifest, lambda data: data["recordSet"].insert(0, record_set("inserted", "y")))
    assert states(project.generate(manifest)) == {"inserted": "created", "rows": "current", "p_pdf": "current"}
    assert {path: text for path, text in project.snapshot().items() if path in reviewed} == reviewed


def test_descriptions_and_equivalent_properties_in_an_annotation_file_change_no_revision(project):
    manifest = project.implemented_study(record_set("rows", "a", "b"))
    reviewed = project.snapshot()
    annotation = project.root / "study/.biotope.yaml"
    annotation.parent.mkdir()
    annotation.write_text(
        "description: A synthetic study.\n"
        "tables:\n"
        "  rows:\n"
        "    description: One row per sample.\n"
        "    columns:\n"
        "      a:\n"
        "        description: The sample.\n"
        "        equivalentProperty: https://schema.org/identifier\n"
    )
    assert project.codes("error") == {}
    assert states(project.generate(manifest)) == {"rows": "current"}
    assert project.snapshot() == reviewed
    rows = json.loads(manifest.read_text())["recordSet"][0]
    assert (rows["description"], rows["field"][0]["equivalentProperty"]) == (
        "One row per sample.",
        "https://schema.org/identifier",
    )
    project.edit(manifest, lambda data: data["recordSet"][0]["field"].append(record_set("rows", "c")["field"][0]))
    assert [finding["subject"] for finding in project.findings() if finding["code"] == "source.drift"] == ["study/rows"]


def test_a_new_column_a_changed_type_and_a_changed_file_reference_drift(project):
    paper = file_object("paper", "p.pdf", fmt="application/pdf")
    other = file_object("other", "other.csv")
    manifest = project.implemented_study(record_set("rows", "a", "b"), files=[paper, other])

    def drift():
        return {finding["subject"] for finding in project.findings() if finding["code"] == "source.drift"}

    def fields(data):
        return data["recordSet"][0]["field"]

    for change, drifted in (
        (lambda data: fields(data).append(record_set("rows", "c")["field"][0]), "study/rows"),
        (lambda data: fields(data)[0].update(dataType="sc:Integer"), "study/rows"),
        (lambda data: fields(data)[1]["source"]["fileObject"].update({"@id": "other"}), "study/rows"),
        (lambda data: data["distribution"][1].update(contentUrl="papers/p.pdf"), "study/p_pdf"),
    ):
        project.edit(manifest, change)
        assert drift() == {drifted}
        project.generate(manifest)
        project.acknowledge_drift(manifest)
        assert not drift()
    project.edit(manifest, lambda data: data["recordSet"][0]["field"].reverse())
    assert drift() == {"study/rows"}


def test_a_build_fails_on_drift_and_generation_never_rewrites_a_drifted_schema(project):
    manifest = project.study(record_set("rows", "x"))
    project.generate(manifest)
    schema = project.sources / "study/rows/schema.py"
    reviewed = schema.read_bytes()
    project.edit(manifest, lambda data: data["recordSet"][0]["field"][0].update(dataType="sc:Integer"))
    result = project.run("graph", "build")
    assert result.exit_code != 0 and "changed since revision" in result.output
    assert states(project.generate(manifest)) == {"rows": "drift"}
    assert schema.read_bytes() == reviewed


def test_reordering_record_sets_without_an_id_is_drift_never_a_conflict(project):
    positional = [
        {"name": "alpha", "field": [{"name": "a", "dataType": "sc:Text"}]},
        {"name": "beta", "field": [{"name": "b", "dataType": "sc:Integer"}]},
    ]
    manifest = project.manifest("study", positional)
    project.generate(manifest)
    project.edit(manifest, lambda data: data["recordSet"].reverse())
    # Their identity is their position, so refusing here would leave no regeneration that could succeed.
    reordered = plan_sources(manifest, project.sources)
    assert states(reordered) == {"alpha": "drift", "beta": "drift"} and not reordered.conflicts
