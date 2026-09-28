"""Source generation: which inputs get packages, how packages are named and owned, and when nothing is written."""

import dataclasses
import json
import re
import shutil

import pytest
from synthetic import Project, file_object, pdf, record_set, states

from biotope.graph import Pipeline, Topology
from biotope.graph.check import check_types
from biotope.graph.discovery import read_declaration
from biotope.graph.inventory import apply_plan, generate_source_packages, plan_sources
from biotope.graph.render import render_inventory
from biotope.graph.reports import PythonCheckFailed
from biotope.graph.sources import LEGACY_HEADER, check_source_record, read_metadata, record_set_targets
from biotope.graph.standardization import field_bindings
from biotope.graph.targets import manifest_targets
from biotope.graph.workspace import select_workspace


def test_multiple_manifests_are_reconciled_one_at_a_time(project):
    first = project.manifest("first", [record_set("a", "x")], [file_object("data", "a.csv")])
    second = project.manifest("second", [record_set("b", "y")], [file_object("data", "b.csv")])
    project.generate(first)
    project.generate(second)
    before = project.snapshot()
    third = project.manifest("third", [record_set("c", "z")], [file_object("data", "c.csv")])
    assert states(project.generate(third)) == {"c": "created"}
    assert {path: code for path, code in project.snapshot().items() if path in before} == before
    project.edit(first, lambda data: data["recordSet"].append(record_set("a2", "w")))
    assert project.codes("error")["inventory.stale"] == ["first/a2"]
    unrelated = {path: code for path, code in project.snapshot().items() if "/first/" not in str(path)}
    assert states(project.generate(first)) == {"a": "current", "a2": "created"}
    assert {path: project.snapshot()[path] for path in unrelated} == unrelated
    assert (project.sources / "inventory.py").read_text() == render_inventory()
    with select_workspace(project.graph) as workspace:
        names = [source.name for source in workspace.pipeline().source_inventory]
    assert names == ["first/a", "first/a2", "second/b", "third/c"]


def test_documents_images_containers_and_file_sets_get_the_right_packages(project):
    listed_as_pdf = file_object("protocol", "raw/protocol.bin", name="protocol.bin")
    listed_as_pdf["encodingFormat"] = ["application/pdf"]
    manifest = project.manifest(
        "study",
        [record_set("table", "x", file="table-file")],
        [
            file_object("table-file", "table.csv"),
            file_object("notes-file", "raw/notes.txt", name="notes.txt", fmt="text/plain"),
            file_object("figure", "raw/figure.png", fmt="image/png"),
            listed_as_pdf,
            file_object("archive", "raw/bundle.zip", name="bundle.zip", fmt="application/zip"),
            {
                "@id": "tiles",
                "@type": "cr:FileSet",
                "name": "tiles",
                "containedIn": {"@id": "archive"},
                "includes": "*.tif",
            },
        ],
    )
    plan = project.generate(manifest)
    packages = ("table", "notes_txt", "figure_png", "protocol_bin", "tiles")
    assert states(plan) == dict.fromkeys(packages, "created")
    schema = {package: (project.sources / "study" / package / "schema.py").read_text() for package in packages}
    assert '__file_object__: ClassVar[str] = "notes-file"' in schema["notes_txt"]
    assert "page or section locations" in schema["notes_txt"] and "page or section locations" in schema["protocol_bin"]
    assert "Describe this file with a RecordSet" in schema["figure_png"] and "or exclude it" in schema["figure_png"]
    assert '__file_set__: ClassVar[str] = "tiles"' in schema["tiles"]
    assert not (project.sources / "study/bundle_zip").exists() and not (project.sources / "study/table_csv").exists()
    project.mark_implemented(*(f"study/{package}" for package in packages))
    assert project.codes("error") == {}


def test_a_generated_schema_binds_and_types_every_field_shape_and_imports_without_its_manifest(project):
    fields = [
        {"@id": "t/", "dataType": "sc:Text"},
        {"@id": "t/a", "name": "dup", "dataType": "sc:Text"},
        {"@id": "t/b", "name": "dup", "dataType": "sc:Integer"},
        {"@id": "t/x y", "name": "x y", "dataType": "sc:Text"},
        {"@id": "t/suffix", "name": "display", "dataType": "sc:Text", "source": {"extract": {"column": "column"}}},
        {"@id": "t/t/inner", "name": "inner", "dataType": "sc:Text"},
        {"@id": "t/class", "name": "class", "dataType": "sc:Text"},
        {"@id": "t/frozenset", "name": "frozenset", "dataType": "sc:Text"},
        {"name": "positional", "dataType": "sc:Float"},
        {
            "@id": "t/nested",
            "name": "nested",
            "subField": [{"@id": "t/nested/leaf", "name": "leaf", "dataType": "sc:Text"}],
        },
        {"name": "details", "repeated": True, "subField": {"name": "label", "dataType": "sc:Text"}},
        {"@id": "t/plain", "name": "plain", "dataType": "sc:Boolean", "biotope:nullable": False},
        {"@id": "t/matrix", "name": "matrix", "dataType": "cr:Float32", "cr:arrayShape": "100,200"},
        {
            "@id": "t/custom",
            "name": "custom",
            "dataType": "custom:Unresolved",
            "description": "Curated prose stays in Croissant.",
            "custom:review": {"evidence": "Curator's note"},
        },
    ]
    manifest = project.manifest("study", [{"@id": "t", "field": fields}])
    project.generate(manifest)
    text = (project.sources / "study/t/schema.py").read_text()
    assert "Curated prose stays in Croissant." not in text and "Curator's note" not in text
    stashed = manifest.rename(project.root / "stashed.jsonld")
    with project.imported("graph.sources.study.t.schema") as module:
        stashed.rename(manifest)
        record = module.T
        assert field_bindings(record) == {
            "t": "t/",
            "dup": "t/a",
            "dup_2": "t/b",
            "x_y": "t/x y",
            "display": "t/suffix",
            "inner": "t/t/inner",
            "class_": "t/class",
            "frozenset_2": "t/frozenset",
            "positional": "t/field/8",
            "nested": "t/nested",
            "details": "t/field/10",
            "plain": "t/plain",
            "matrix": "t/matrix",
            "custom": "t/custom",
        }
        assert field_bindings(module.TNested) == {"leaf": "t/nested/leaf"}
        assert field_bindings(module.TDetails) == {"label": "t/field/10/subField"}
        assert "source" not in {field.name: field for field in dataclasses.fields(record)}["plain"].metadata
        annotations = record.__annotations__
        assert (annotations["plain"], annotations["positional"]) == ("bool", "float | None")
        assert annotations["details"].startswith("list[")
        assert "UnknownValue" in annotations["matrix"] and "UnknownValue" in annotations["custom"]
        assert record.__missing_values__ == frozenset({""})
        assert check_source_record(read_metadata(manifest), record) == record.__source_digest__
    project.mark_implemented("study/t")
    assert project.codes("error") == {}
    assert project.codes("warning")["source.opaque"] == ["study/t.T.matrix", "study/t.T.custom"]


def test_generated_schemas_pass_strict_pyright_while_opaque_values_stay_opaque(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    columns = [{"name": f"column_{column}", "dataType": "sc:Text"} for column in range(3)]
    manifests = {
        "tables": {"recordSet": [{"name": f"table_{table}", "field": columns} for table in range(3)]},
        "opaque": {"recordSet": [{"name": "opaque", "field": [{"name": "image", "dataType": "custom:Image"}]}]},
    }
    sources = tmp_path / "sources"
    for name, data in manifests.items():
        (tmp_path / f"{name}.jsonld").write_text(json.dumps(data))
        generate_source_packages(tmp_path / f"{name}.jsonld", sources)
    probe = sources / "opaque/probe.py"
    probe.write_text("from .opaque.schema import Opaque\n\n\ndef label(row: Opaque) -> str:\n    return row.image\n")
    pipeline = Pipeline("types", Topology((), ()), (), (), lambda ctx: None, scope="generated", code_paths=(sources,))
    with pytest.raises(PythonCheckFailed) as failure:
        check_types(pipeline)
    [finding] = failure.value.findings
    assert finding.location.path == str(probe) and "UnknownValue" in finding.message


def test_an_incomplete_package_is_completed_without_overwriting(project):
    manifest = project.study(record_set("rows", "x"), record_set("next", "y"))
    project.generate(manifest)
    (project.sources / "study/rows/loader.py").unlink()
    schema = project.sources / "study/rows/schema.py"
    schema.write_text(schema.read_text().replace("class Rows:", "class Renamed:"))
    registration = project.sources / "study/rows/__init__.py"
    registration.unlink()
    shutil.rmtree(project.sources / "study/next")
    (project.sources / "study/next").mkdir()
    (project.sources / "study/next/notes.md").write_text("authored notes\n")
    edited = schema.read_bytes()
    plan = project.generate(manifest)
    assert states(plan) == {"rows": "completed", "next": "completed"}
    assert schema.read_bytes() == edited
    assert "records=(Renamed,)" in registration.read_text()
    assert (project.sources / "study/next/notes.md").read_text() == "authored notes\n"
    assert {path.name for path in (project.sources / "study/next").iterdir()} == {
        "notes.md",
        "schema.py",
        "__init__.py",
        "loader.py",
    }
    assert set(states(project.generate(manifest)).values()) == {"current"}


def test_collection_skips_helpers_hidden_directories_and_symlinks_and_requires_a_registration(project):
    manifest = project.implemented_study(record_set("rows", "x"))
    root = project.sources / "study"
    (root / "_shared.py").write_text('"""A decoding helper."""\n')
    (root / "_helpers").mkdir()
    (root / "_helpers/__init__.py").write_text('"""An authored helper package."""\n')
    shutil.copytree(root / "rows", root / ".rows.staging")
    (root / "alias").symlink_to(root / "rows", target_is_directory=True)
    assert states(plan_sources(manifest, project.sources)) == {"rows": "current"}
    with select_workspace(project.graph) as workspace:
        assert [source.name for source in workspace.pipeline().source_inventory] == ["study/rows"]
    assert project.codes("error") == {}
    (root / "rows/__init__.py").write_text('"""Not registered yet."""\n')
    [message] = project.messages("workspace.load")
    assert "a source package registers SOURCE = SourceContract(...)" in message


def test_a_renamed_package_directory_and_class_stay_owned_by_their_identity(project):
    manifest = project.implemented_study(record_set("rows", "x"))
    (project.sources / "study/rows").rename(project.sources / "study/samples")
    for name in ("schema.py", "__init__.py", "loader.py"):
        path = project.sources / "study/samples" / name
        path.write_text(path.read_text().replace("Rows", "Sample"))
    plan = project.generate(manifest)
    assert states(plan) == {"samples": "current"}
    assert sorted(path.name for path in (project.sources / "study").iterdir() if path.is_dir()) == ["samples"]
    assert not project.codes("error")


def test_a_renamed_file_resource_leaves_an_orphan_with_a_rebind_hint(project):
    manifest = project.manifest("study", [], [pdf("doc-1", "raw/paper.pdf")])
    project.generate(manifest)
    project.mark_implemented("study/paper_pdf")
    project.edit(manifest, lambda data: data["distribution"][0].update({"@id": "doc-2"}))
    plan = project.generate(manifest)
    [orphan] = [status for status in plan.statuses if status.state == "orphaned"]
    [created] = [status for status in plan.statuses if status.state == "created"]
    assert orphan.package == "paper_pdf" and created.identity == "doc-2"
    hint = "'doc-2' now describes the same file (raw/paper.pdf)"
    assert hint in orphan.detail and f"delete {created.package}/" in orphan.detail
    [message] = project.messages("inventory.orphan")
    assert hint in message


LEGACY_SCHEMA = """{header}# biotope:record-set {{"id":"rows"}}
from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, TypeAlias

GENERATOR_VERSION = '5'
SOURCE_DIGEST = '{revision}'

@dataclass(frozen=True, kw_only=True)
class Rows:
    __record_set__: ClassVar[str] = 'rows'
    __source_digest__: ClassVar[str] = SOURCE_DIGEST

    value: str | None = None

    __field_refs__: ClassVar[dict[str, str]] = {{
        'value': 'rows/value',
    }}


RECORDS: tuple[type, ...] = (Rows,)
SourceRow: TypeAlias = Rows
"""

LEGACY_ROOT = """{header}# biotope:manifest {{"metadata":"../../../.biotope/datasets/study.jsonld","packages":["rows"]}}
\"\"\"Generated inventory of every record set described by study.jsonld.\"\"\"

from __future__ import annotations

from biotope.graph import SourceContract

from . import rows


CONTRACTS: tuple[SourceContract, ...] = (rows.SOURCE,)
"""

LEGACY_REGISTRATION = '''"""Project-owned source registration."""

from pathlib import Path

from biotope.graph import SourceContract

from .schema import RECORDS


SOURCE = SourceContract(
    name="study/rows",
    metadata=Path(__file__).resolve().parent / "../../../../.biotope/datasets/study.jsonld",
    schema=Path(__file__).with_name("schema.py"),
    records=RECORDS,
)
'''


def test_a_09_package_is_adopted_and_its_root_rewritten(project):
    manifest = project.study(record_set("rows", "value"))
    [target] = manifest_targets(read_metadata(manifest))
    package = project.sources / "study/rows"
    package.mkdir(parents=True)
    (package / "schema.py").write_text(LEGACY_SCHEMA.format(header=LEGACY_HEADER, revision=target.revision))
    (package / "__init__.py").write_text(LEGACY_REGISTRATION)
    (package / "loader.py").write_text("def load(config):\n    return iter(())\n")
    (project.sources / "study/__init__.py").write_text(LEGACY_ROOT.format(header=LEGACY_HEADER))
    (project.sources / "inventory.py").unlink()
    plan = project.generate(manifest)
    assert states(plan) == {"rows": "current"}
    assert {path.name for path in plan.generated_files} == {"__init__.py", "inventory.py"}
    assert (project.sources / "study/__init__.py").read_text().startswith("# Generated by biotope;")
    assert (package / "schema.py").read_text().startswith(LEGACY_HEADER)
    assert project.codes("error") == {}
    with select_workspace(project.graph) as workspace:
        [source] = workspace.pipeline().source_inventory
        assert source.name == "study/rows" and source.records[0].__name__ == "Rows"


def test_a_class_declared_identity_wins_over_a_stale_09_marker(tmp_path):
    schema = tmp_path / "schema.py"
    schema.write_text(
        f'{LEGACY_HEADER}# biotope:record-set {{"id":"rows"}}\n'
        "class Rows:\n    __record_set__ = 'rows_v2'\n    __source_digest__ = 'abc'\n"
    )
    declaration = read_declaration(schema)
    assert (declaration.identity, declaration.problem) == ("rows_v2", "")
    schema.write_text(f'{LEGACY_HEADER}# biotope:record-set {{"id":"rows"}}\nx = 1\n')
    assert read_declaration(schema).identity == "rows"


def test_a_nested_field_scoped_elsewhere_does_not_become_a_second_identity(project):
    nested = {"@id": "elsewhere/nested", "subField": [{"@id": "elsewhere/nested/leaf", "dataType": "sc:Text"}]}
    manifest = project.manifest("study", [{"@id": "t", "field": [nested]}])
    project.generate(manifest)
    assert read_declaration(project.sources / "study/t/schema.py").identity == "t"
    assert states(project.generate(manifest)) == {"t": "current"}


def test_a_record_class_never_shadows_the_names_its_templates_import(project):
    shadowing = ("path", "iterator", "source_record", "run_context")
    project.implemented_study(*(record_set(identity, "x") for identity in shadowing))
    for identity in shadowing:
        with project.imported(f"graph.sources.study.{identity}.loader") as loader:
            assert loader.SOURCE.records[0].__name__.endswith("Record")
    assert "workspace.load" not in project.codes()


def test_a_new_package_never_takes_a_name_in_use(project):
    manifest = project.study(record_set("kept", "x"), record_set("paper_pdf", "y"), files=[pdf("doc", "raw/paper.pdf")])
    project.generate(manifest)
    (project.sources / "study/samples.py").write_text('"""A helper module."""\n')
    project.edit(
        manifest, lambda data: data["recordSet"].extend([record_set("kept.", "z"), record_set("samples", "w")])
    )
    names = {status.identity: status.package for status in plan_sources(manifest, project.sources).statuses}
    assert (names["kept"], names["paper_pdf"]) == ("kept", "paper_pdf")
    for identity, taken in (("doc", "paper_pdf"), ("kept.", "kept"), ("samples", "samples")):
        assert names[identity].startswith(f"{taken}_")


def test_record_set_package_names_are_readable_order_independent_and_collision_safe():
    def targets(identities):
        return record_set_targets({"recordSet": [{"@id": identity, "field": []} for identity in identities]})

    exported_tables = [
        "LAA_final_table",
        "hill_af_corrected",
        "study_metadata_Tabelle1",
        "44161_2025_626_MOESM3_ESM.xlsx_-_SupTable5",
        "44161_2025_626_MOESM3_ESM.xlsx_-_Top_100_marker_genes_for_each_cell-type",
    ]
    projected = targets(exported_tables)
    assert [target.package for target in projected] == [
        "LAA_final_table",
        "hill_af_corrected",
        "study_metadata_Tabelle1",
        "_44161_2025_626_MOESM3_ESM_xlsx_SupTable5",
        "_44161_2025_626_MOESM3_ESM_xlsx_Top_100_marker_genes_for_each_cell_type",
    ]
    assert [target.class_name for target in projected] == [
        "LAAFinalTable",
        "HillAfCorrected",
        "StudyMetadataTabelle1",
        "Record_44161_2025_626_MOESM3_ESM_xlsx_SupTable5",
        "Record_44161_2025_626_MOESM3_ESM_xlsx_Top_100_marker_genes_for_each_cell_type",
    ]
    assert {t.identity: t.package for t in targets(exported_tables)} == {
        t.identity: t.package for t in targets(exported_tables[::-1])
    }
    # A compatibility pin: authored loaders import these names, so changing digest() or its truncation renames them.
    assert [target.package for target in targets(["a.b", "a-b", "c"])] == ["a_b_12734df7", "a_b_4a3ef97a", "c"]
    assert len({target.package for target in targets(["a.b", "a-b", "a_b_12734df7"])}) == 3
    [unnamed] = record_set_targets({"recordSet": [{"name": "Plain rows", "field": []}]})
    assert (unnamed.identity, unnamed.package) == ("/recordSet/0", "Plain_rows")
    for reserved in ("loader", "schema", "RECORDS", "SourceRow", "UnknownValue", "CONTRACTS"):
        [target] = targets([reserved])
        assert target.package.startswith(f"{reserved}_")


def test_a_root_needs_a_real_sources_directory_and_an_unreserved_name(project):
    manifest = project.study(record_set("rows", "x"))
    for name in ("__study", "inventory"):
        with pytest.raises(ValueError, match="not a usable root package name"):
            plan_sources(manifest, project.sources, name)
    linked = project.graph / "linked"
    linked.symlink_to(project.sources, target_is_directory=True)
    for out in (project.sources / "inventory.py", project.graph / "sources.py", linked):
        with pytest.raises(ValueError, match="is not a directory"):
            plan_sources(manifest, out)


def test_a_symlinked_manifest_renders_the_same_root(project):
    real = project.manifest("study-v2", [record_set("rows", "x")], [file_object("data", "d")])
    link = real.with_name("study.jsonld")
    link.symlink_to(real.name)
    project.generate(link, "study")
    project.mark_implemented("study/rows")
    assert "inventory.stale" not in project.codes()
    assert states(project.generate(link, "study")) == {"rows": "current"}
    assert not plan_sources(link, project.sources, "study").generated_files


def test_a_generated_root_file_is_rewritten_only_when_its_normalized_text_differs(project):
    manifest = project.study(record_set("rows", "x"))
    project.generate(manifest)
    root = project.sources / "study/__init__.py"
    root.write_text(root.read_text().replace("\n\n\nCONTRACTS", "\n\n\n\n   \nCONTRACTS") + "\n\n")
    assert not plan_sources(manifest, project.sources).generated_files
    root.write_text(root.read_text().replace("collected when imported", "collected on import"))
    assert [path.name for path in plan_sources(manifest, project.sources).generated_files] == ["__init__.py"]


def test_a_contested_package_or_root_is_a_conflict_that_writes_nothing(project):
    manifest = project.study(record_set("rows", "x"))
    project.generate(manifest)
    shutil.copytree(project.sources / "study/rows", project.sources / "study/copy")
    before = project.snapshot()
    plan = plan_sources(manifest, project.sources)
    assert {status.package for status in plan.conflicts} == {"rows", "copy"}
    with pytest.raises(ValueError, match="also declared"):
        apply_plan(plan)
    assert project.snapshot() == before
    assert set(project.codes("error")["inventory.conflict"]) == {"study/rows", "study/copy"}
    shutil.rmtree(project.sources / "study/copy")
    assert "already generated into root 'study'" in plan_sources(manifest, project.sources, "again").conflicts[0].detail
    twin = project.root / ".biotope/datasets/other/study.jsonld"
    twin.parent.mkdir()
    twin.write_text(manifest.read_text())
    assert "pass --package" in plan_sources(twin, project.sources).conflicts[0].detail
    assert states(project.generate(twin, "study_other")) == {"rows": "created"}


def author_the_root(project):
    (project.sources / "study/__init__.py").write_text('"""Registration authored under the single-module layout."""\n')


def restore_the_single_module_layout(project):
    (project.sources / "study/schema.py").write_text("# Generated by biotope.graph; edit curated Croissant.\n")


def symlinked(relative):
    def move_behind_a_symlink(project):
        target, elsewhere = project.sources / relative, project.root.parent / "elsewhere"
        shutil.move(str(target), str(elsewhere))
        target.symlink_to(elsewhere, target_is_directory=elsewhere.is_dir())

    return move_behind_a_symlink


@pytest.mark.parametrize(
    ("occupy", "detail"),
    [
        pytest.param(author_the_root, "authored code occupies the generated root inventory", id="authored-root"),
        pytest.param(restore_the_single_module_layout, "single-module layout", id="single-module"),
        pytest.param(
            Project.author_inventory, "authored code occupies the generated inventory.py", id="authored-inventory"
        ),
        pytest.param(symlinked("study"), "the root is a symlink", id="symlinked-root"),
        pytest.param(symlinked("study/__init__.py"), "the root inventory is a symlink", id="symlinked-root-init"),
        pytest.param(symlinked("inventory.py"), "inventory.py is a symlink", id="symlinked-inventory"),
    ],
)
def test_a_generated_file_that_is_authored_or_symlinked_is_a_conflict(project, occupy, detail):
    manifest = project.study(record_set("rows", "x"))
    project.generate(manifest)
    occupy(project)
    [conflict] = plan_sources(manifest, project.sources).conflicts
    assert detail in conflict.detail


@pytest.mark.parametrize(
    ("distribution", "detail"),
    [
        pytest.param(
            [file_object("data", "a.csv"), file_object("data", "b.csv")],
            "2 entries in study.jsonld share the @id 'data'",
            id="covered-file-objects",
        ),
        pytest.param(
            [file_object("data", "a.csv"), {"@id": "data", "@type": "cr:FileSet", "includes": "*.csv"}],
            "2 entries in study.jsonld share the @id 'data'",
            id="covered-across-kinds",
        ),
        pytest.param(
            [file_object("data", "a.csv", contained="zip"), file_object("zip", "a.zip"), file_object("zip", "b.zip")],
            "2 entries in study.jsonld share the @id 'zip'",
            id="duplicate-containers",
        ),
        pytest.param(
            [file_object("data", "d"), pdf("doc", "raw/a.pdf"), pdf("doc", "raw/b.pdf")],
            "2 entries in study.jsonld share the @id 'doc'",
            id="duplicate-documents",
        ),
        pytest.param(
            [
                file_object("data", "d"),
                {"@type": "cr:FileObject", "name": "protocol.pdf", "contentUrl": "protocol.pdf"},
            ],
            "the FileObject at /distribution/1 (protocol.pdf) in study.jsonld has no @id",
            id="file-without-id",
        ),
    ],
)
def test_a_shared_or_missing_manifest_id_is_a_conflict_that_writes_nothing(project, distribution, detail):
    manifest = project.manifest("study", [record_set("rows", "x")], distribution)
    files, history = project.snapshot(), set(project.store)
    plan = plan_sources(manifest, project.sources)
    [conflict] = plan.conflicts
    assert detail in conflict.detail
    assert {status.identity: status.state for status in plan.statuses} == {None: "conflict", "rows": "created"}
    with pytest.raises(ValueError, match=re.escape(detail)):
        project.generate(manifest)
    assert project.snapshot() == files and set(project.store) == history


def claim_another_source(project):
    second = (project.sources / "study/b/schema.py").read_text().split("@dataclass", 1)[1]
    schema = project.sources / "study/a/schema.py"
    undigested = "\n".join(line for line in second.splitlines() if "digest" not in line)
    schema.write_text(schema.read_text() + "\n\n@dataclass" + undigested)
    shutil.rmtree(project.sources / "study/b")


def move_into_an_unimportable_directory(project):
    (project.sources / "study/a").rename(project.sources / "study/a-v2")


@pytest.mark.parametrize(
    ("contest", "conflict"),
    [
        pytest.param(claim_another_source, ("a", "b"), id="schema-declaring-two-sources"),
        pytest.param(move_into_an_unimportable_directory, ("a-v2", "a"), id="unimportable-directory"),
    ],
)
def test_a_contested_identity_gets_no_package_while_the_rest_is_reconciled(project, contest, conflict):
    manifest = project.implemented_study(record_set("a", "x"), record_set("b", "y"))
    contest(project)
    project.edit(manifest, lambda data: data["recordSet"].append(record_set("later", "z")))
    plan = plan_sources(manifest, project.sources)
    assert [(status.package, status.identity) for status in plan.conflicts] == [conflict]
    assert [status.identity for status in plan.statuses if status.state == "created"] == ["later"]
    assert project.codes("error")["inventory.conflict"] == [f"study/{conflict[0]}"]


def test_an_ambiguous_schema_is_a_conflict_that_blocks_every_new_package(project):
    manifest = project.implemented_study(record_set("rows", "x"))
    schema = project.sources / "study/rows/schema.py"
    schema.write_text(schema.read_text() + '\n\n@dataclass(frozen=True)\nclass Copy:\n    __record_set__ = "rows"\n')
    project.edit(manifest, lambda data: data["recordSet"].append(record_set("later", "y")))
    plan = plan_sources(manifest, project.sources)
    [conflict] = plan.conflicts
    assert "several classes declare 'rows': Rows, Copy" in conflict.detail
    assert not plan.new_packages and "created" not in states(plan).values()


def describe_rows_as_a_file(project, manifest):
    def change(data):
        data["recordSet"].clear()
        data["distribution"].append(pdf("rows", "raw/rows.pdf"))

    project.edit(manifest, change)


def reduce_to_a_09_marker_without_a_loader(project, manifest):
    (project.sources / "study/rows/schema.py").write_text(f'{LEGACY_HEADER}# biotope:record-set {{"id":"rows"}}\n')
    (project.sources / "study/rows/loader.py").unlink()


@pytest.mark.parametrize(
    ("change", "detail"),
    [
        pytest.param(
            describe_rows_as_a_file,
            "declares record set 'rows', but the manifest describes a FileObject",
            id="kind-changed",
        ),
        pytest.param(
            reduce_to_a_09_marker_without_a_loader,
            "cannot complete the package: no class declares its identity",
            id="incomplete-without-a-class",
        ),
    ],
)
def test_a_package_that_cannot_serve_its_target_is_a_conflict(project, change, detail):
    manifest = project.study(record_set("rows", "x"))
    project.generate(manifest)
    change(project, manifest)
    conflicts = plan_sources(manifest, project.sources).conflicts
    assert [(status.package, status.detail) for status in conflicts] == [("rows", detail)]
