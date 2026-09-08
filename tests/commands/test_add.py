"""Tests for the add command."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.add import _add_file, _bake_directory, add
from biotope.utils import (
    calculate_file_checksum,
    is_file_tracked,
    stage_git_changes,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_file(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("This is a test file content")
    return file_path


@pytest.fixture
def biotope_project(tmp_path):
    (tmp_path / ".biotope" / "datasets").mkdir(parents=True)
    (tmp_path / ".git").mkdir()
    return tmp_path


@pytest.fixture
def git_repo(biotope_project):
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        yield biotope_project


def test_calculate_file_checksum(sample_file):
    import hashlib

    expected_hash = hashlib.sha256(sample_file.read_bytes()).hexdigest()
    assert calculate_file_checksum(sample_file) == expected_hash


def test_stage_git_changes(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    manifest = tmp_path / ".biotope/datasets/items.jsonld"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}")
    stage_git_changes(tmp_path)
    staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=tmp_path, text=True)
    assert ".biotope/datasets/items.jsonld" in staged.splitlines()


def test_add_file_absolute_path_writes_cr_file_object(git_repo, sample_file):
    target_file = git_repo / sample_file.name
    target_file.write_text(sample_file.read_text())

    datasets_dir = git_repo / ".biotope" / "datasets"
    result = _add_file(target_file, git_repo, datasets_dir, False)
    assert result is True

    metadata_file = datasets_dir / target_file.relative_to(git_repo).with_suffix(".jsonld")
    assert metadata_file.exists()

    with open(metadata_file) as handle:
        metadata = json.load(handle)

    assert metadata["distribution"][0]["@type"] == "cr:FileObject"
    assert metadata["distribution"][0]["contentUrl"] == str(target_file.relative_to(git_repo))
    assert is_file_tracked(target_file, git_repo)


def test_add_file_relative_path_already_tracked(git_repo):
    data_dir = git_repo / "data" / "inputs"
    data_dir.mkdir(parents=True)
    target_file = data_dir / "experiment.csv"
    target_file.write_text("gene,expression\nBRCA1,12.5")

    datasets_dir = git_repo / ".biotope" / "datasets"

    original_cwd = Path.cwd()
    try:
        os.chdir(git_repo)
        relative_path = Path("data/inputs/experiment.csv")
        assert _add_file(relative_path, git_repo, datasets_dir, False) is True
        assert _add_file(relative_path, git_repo, datasets_dir, False) is False
        assert _add_file(relative_path, git_repo, datasets_dir, True) is True
    finally:
        os.chdir(original_cwd)


def test_add_file_stamps_status_raw_by_default(git_repo):
    """A plain file `biotope add` without a baked record set lands as raw."""
    from biotope.metadata import STATUS_RAW, get_status

    target = git_repo / "doc.txt"
    target.write_text("a free-text doc")
    datasets_dir = git_repo / ".biotope" / "datasets"
    assert _add_file(target, git_repo, datasets_dir, False) is True

    manifest = datasets_dir / "doc.jsonld"
    with open(manifest) as f:
        metadata = json.load(f)
    assert get_status(metadata) == STATUS_RAW


def test_add_file_status_override(git_repo):
    """`--status processed` overrides the heuristic."""
    from biotope.metadata import STATUS_PROCESSED, get_status

    target = git_repo / "doc.txt"
    target.write_text("ignore me")
    datasets_dir = git_repo / ".biotope" / "datasets"
    _add_file(
        target,
        git_repo,
        datasets_dir,
        False,
        overrides={**_default_overrides_for_test(), "status_override": "processed"},
    )

    manifest = datasets_dir / "doc.jsonld"
    with open(manifest) as f:
        metadata = json.load(f)
    assert get_status(metadata) == STATUS_PROCESSED


def test_resolve_dataset_ref_accepts_three_forms(tmp_path):
    """Canonical id, data-path, and manifest-path all resolve to the rel id."""
    from biotope.commands.add import _resolve_dataset_ref

    project = tmp_path / "proj"
    datasets_dir = project / ".biotope" / "datasets" / "data" / "inputs"
    datasets_dir.mkdir(parents=True)

    data_file = project / "data" / "inputs" / "kidney.pdf"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text("pdf")

    manifest = datasets_dir / "kidney.jsonld"
    manifest.write_text("{}")

    canonical = "data/inputs/kidney"
    assert _resolve_dataset_ref(canonical, project) == canonical
    assert _resolve_dataset_ref(str(data_file), project) == canonical
    assert _resolve_dataset_ref(str(manifest), project) == canonical


def test_resolve_dataset_ref_rejects_missing(tmp_path):
    from biotope.commands.add import _resolve_dataset_ref

    project = tmp_path / "proj"
    (project / ".biotope" / "datasets").mkdir(parents=True)
    with pytest.raises(ValueError, match="no manifest found"):
        _resolve_dataset_ref("missing/dataset", project)


def test_add_file_derived_from_writes_provenance(git_repo):
    """`--derived-from <ref>` records `prov:wasDerivedFrom` on the new dataset."""
    from biotope.metadata import get_derived_from

    # Seed an existing manifest to derive from.
    src_manifest = git_repo / ".biotope" / "datasets" / "raw_pdf.jsonld"
    src_manifest.parent.mkdir(parents=True, exist_ok=True)
    src_manifest.write_text(
        json.dumps(
            {
                "@type": "sc:Dataset",
                "name": "raw_pdf",
                "distribution": [],
                "biotope:status": "raw",
            }
        )
    )

    target = git_repo / "extracted.json"
    target.write_text("{}")
    datasets_dir = git_repo / ".biotope" / "datasets"
    _add_file(
        target,
        git_repo,
        datasets_dir,
        False,
        overrides={**_default_overrides_for_test(), "derived_from": ["raw_pdf"]},
    )

    with open(datasets_dir / "extracted.jsonld") as f:
        metadata = json.load(f)
    assert get_derived_from(metadata) == ["raw_pdf"]


def _default_overrides_for_test():
    from biotope.commands.add import _default_overrides

    return _default_overrides()


def test_is_file_tracked_recognises_fileset_coverage(tmp_path):
    """A file covered only by a `cr:FileSet` glob in a multi-file manifest is
    still tracked. Regression: the old `is_file_tracked` matched only
    explicit `cr:FileObject.contentUrl` and missed the common
    `biotope add <dir>` shape where structured files are covered by a glob."""
    from biotope.utils import is_file_tracked

    project_root = tmp_path / "proj"
    data_dir = project_root / "data" / "ot" / "target"
    data_dir.mkdir(parents=True)
    (project_root / ".biotope" / "datasets" / "data" / "ot").mkdir(parents=True)

    (data_dir / "part-00.parquet").write_bytes(b"x")
    (data_dir / "part-01.parquet").write_bytes(b"y")
    (data_dir / "README.md").write_text("notes")

    manifest = project_root / ".biotope" / "datasets" / "data" / "ot" / "target.jsonld"
    manifest.write_text(
        json.dumps(
            {
                "@type": "sc:Dataset",
                "name": "data/ot/target",
                "distribution": [
                    {"@type": "cr:FileSet", "@id": "fs", "includes": "*.parquet"},
                    {
                        "@type": "cr:FileObject",
                        "@id": "fo_readme",
                        "contentUrl": "data/ot/target/README.md",
                        "sha256": "deadbeef",
                        "contentSize": "5",
                    },
                ],
            }
        )
    )

    # FileSet-covered: previously missed; now tracked.
    assert is_file_tracked(data_dir / "part-00.parquet", project_root)
    assert is_file_tracked(data_dir / "part-01.parquet", project_root)
    # Explicit FileObject: still tracked.
    assert is_file_tracked(data_dir / "README.md", project_root)
    # Not under the dataset: still not tracked.
    (project_root / "elsewhere.txt").write_text("x")
    assert not is_file_tracked(project_root / "elsewhere.txt", project_root)


def _write_png(path: Path) -> None:
    """A 1x1 PNG, so the image handler claims it and emits a FileSet."""
    from PIL import Image

    Image.new("RGB", (1, 1)).save(path)


def test_glob_covered_files_keep_their_checksum(tmp_path):
    """A FileSet describes structure; it does not stand in for a file's identity.

    Dropping the FileObjects a FileSet glob covers took every checksum with them,
    so `check-data` silently verified a fraction of the files it listed.
    """
    project_root = tmp_path / "project"
    data_dir = project_root / "data" / "images"
    (project_root / ".biotope" / "datasets").mkdir(parents=True)
    data_dir.mkdir(parents=True)
    for name in ("a.png", "b.png"):
        _write_png(data_dir / name)

    metadata_dict, _ = _bake_directory(data_dir, project_root, {})

    file_objects = [d for d in metadata_dict["distribution"] if d.get("@type") == "cr:FileObject"]
    assert any(d.get("@type") == "cr:FileSet" for d in metadata_dict["distribution"])
    assert {Path(d["contentUrl"]).name for d in file_objects} == {"a.png", "b.png"}
    assert all(d.get("sha256") for d in file_objects)


def test_bake_directory_tracks_unparseable_files(tmp_path):
    project_root = tmp_path / "project"
    data_dir = project_root / "data" / "mixed"
    (project_root / ".biotope" / "datasets").mkdir(parents=True)
    data_dir.mkdir(parents=True)

    source_csv = Path("tests/example_gene_expression.csv").resolve()
    (data_dir / "example_gene_expression.csv").write_text(source_csv.read_text())
    (data_dir / "README.md").write_text("notes")

    metadata_dict, n_source_files = _bake_directory(data_dir, project_root, {})

    assert n_source_files == 2
    assert metadata_dict["recordSet"]
    distribution = metadata_dict["distribution"]
    assert any(item["@type"] == "cr:FileObject" for item in distribution)
    assert any(item.get("contentUrl") == "data/mixed/README.md" for item in distribution)

    scaffold_path = data_dir / ".biotope.yaml"
    import yaml

    from biotope.commands.add import _generate_biotope_scaffold_from_baked

    _generate_biotope_scaffold_from_baked(data_dir, metadata_dict, project_root)
    assert scaffold_path.exists()
    payload = yaml.safe_load(scaffold_path.read_text())
    assert isinstance(payload, dict)
    assert isinstance(payload["dataset"], dict)
    assert payload["dataset"]["source_path"] == "data/mixed"
    assert isinstance(payload["record_sets"], list)
    assert payload["record_sets"]


@mock.patch("biotope.commands.add.find_biotope_root")
@mock.patch("biotope.commands.add._bake_directory")
@mock.patch("biotope.commands.add._generate_biotope_scaffold_from_baked")
@mock.patch("biotope.commands.add.stage_git_changes")
def test_add_command_directory_recurses_by_default(
    mock_stage,
    mock_csv,
    mock_bake,
    mock_find_root,
    runner,
    git_repo,
):
    mock_find_root.return_value = git_repo

    data_dir = git_repo / "data"
    data_dir.mkdir()
    fake_metadata = {"recordSet": [{"@id": "#rs", "field": []}], "distribution": []}
    mock_bake.return_value = (fake_metadata, 2)

    with runner.isolated_filesystem():
        os.chdir(git_repo)
        result = runner.invoke(add, [str(data_dir)])

    assert result.exit_code == 0
    mock_bake.assert_called_once()
    mock_stage.assert_called_once_with(git_repo)
    mock_csv.assert_called_once()


@mock.patch("biotope.commands.add.find_biotope_root")
@mock.patch("biotope.commands.add._bake_directory")
@mock.patch("biotope.commands.add._generate_biotope_scaffold_from_baked")
@mock.patch("biotope.commands.add.stage_git_changes")
def test_add_command_directory_already_tracked_skips_without_rebake(
    mock_stage,
    mock_csv,
    mock_bake,
    mock_find_root,
    runner,
    git_repo,
):
    mock_find_root.return_value = git_repo

    data_dir = git_repo / "data"
    data_dir.mkdir()
    fake_metadata = {"recordSet": [{"@id": "#rs", "field": []}], "distribution": []}
    mock_bake.return_value = (fake_metadata, 2)

    with runner.isolated_filesystem():
        os.chdir(git_repo)
        first = runner.invoke(add, [str(data_dir)])
        assert first.exit_code == 0
        mock_bake.assert_called_once()
        # The real `_bake_directory` writes metadata_path; the mock doesn't,
        # so simulate that side effect for the "already tracked" check.
        (git_repo / ".biotope" / "datasets" / "data.jsonld").write_text("{}")

        second = runner.invoke(add, [str(data_dir)])
        assert second.exit_code == 0
        assert "already exists" in second.output
        mock_bake.assert_called_once()  # not called again

        third = runner.invoke(add, ["--rebake", str(data_dir)])
        assert third.exit_code == 0
        assert "Re-baked" in third.output
        assert mock_bake.call_count == 2


@mock.patch("biotope.commands.add.find_biotope_root")
@mock.patch("biotope.commands.add._bake_directory")
@mock.patch("biotope.commands.add._generate_biotope_scaffold_from_baked")
@mock.patch("biotope.commands.add.stage_git_changes")
def test_add_command_resolves_relative_directory(
    mock_stage,
    mock_csv,
    mock_bake,
    mock_find_root,
    runner,
    git_repo,
):
    """Regression: relative dir argument must not break CSV scaffold writing."""
    mock_find_root.return_value = git_repo

    (git_repo / "data").mkdir()
    fake_metadata = {"recordSet": [], "distribution": []}
    mock_bake.return_value = (fake_metadata, 1)

    os.chdir(git_repo)
    result = runner.invoke(add, ["data"])

    assert result.exit_code == 0, result.output
    csv_source_dir = mock_csv.call_args.args[0]
    assert csv_source_dir.is_absolute()
    assert csv_source_dir == (git_repo / "data").resolve()


@mock.patch("biotope.commands.add.find_biotope_root")
def test_add_command_rejects_name_for_multiple_paths(mock_find_root, runner, git_repo):
    mock_find_root.return_value = git_repo

    file_one = git_repo / "one.txt"
    file_two = git_repo / "two.txt"
    file_one.write_text("one")
    file_two.write_text("two")

    with runner.isolated_filesystem():
        os.chdir(git_repo)
        result = runner.invoke(add, ["--name", "dataset", str(file_one), str(file_two)])

    assert result.exit_code != 0
    assert "--name can only be used when adding one path" in result.output


# ---------------------------------------------------------------------------
# croissant-baker integration — run against the real baker, because the last
# break was an import move swallowed by an `except ImportError`.
# ---------------------------------------------------------------------------


EXAMPLE_CSV = Path(__file__).resolve().parents[1] / "example_gene_expression.csv"


@pytest.fixture
def mixed_dataset(tmp_path):
    """A project holding one gzipped CSV the baker reads and one file it cannot."""
    import gzip

    project_root = tmp_path / "project"
    data_dir = project_root / "data" / "mixed"
    (project_root / ".biotope" / "datasets").mkdir(parents=True)
    data_dir.mkdir(parents=True)
    (data_dir / "expression.csv.gz").write_bytes(gzip.compress(EXAMPLE_CSV.read_bytes()))
    (data_dir / "README.md").write_text("notes")
    return project_root, data_dir


@pytest.mark.parametrize("compress", [False, True])
def test_enrich_with_baker_builds_record_set(tmp_path, compress):
    """A single-file add gets a recordSet, whether or not the file is wrapped."""
    import gzip

    from biotope.commands.add import _enrich_with_baker

    payload = EXAMPLE_CSV.read_bytes()
    file_path = tmp_path / ("data.csv.gz" if compress else "data.csv")
    file_path.write_bytes(gzip.compress(payload) if compress else payload)

    metadata = {"distribution": [{"@id": "file_0", "@type": "cr:FileObject"}]}
    _enrich_with_baker(metadata, file_path)

    fields = metadata["recordSet"][0]["field"]
    assert [f["name"] for f in fields] == ["GeneID", "Sample1", "Sample2", "Sample3", "Sample4", "Sample5"]
    assert all(f["source"]["fileObject"]["@id"] == "file_0" for f in fields)


def test_bake_directory_reports_coverage(mixed_dataset, capsys):
    """Undescribed files are otherwise invisible: biotope backfills them like any other."""
    project_root, data_dir = mixed_dataset

    _bake_directory(data_dir, project_root, {})

    out = capsys.readouterr().out
    assert "Scanned 2 file(s): 1 described, 1 not described." in out
    assert "no handler: 1" in out
    metadata = json.loads((project_root / ".biotope" / "datasets" / "data" / "mixed.jsonld").read_text())
    assert metadata["recordSet"]
    objects = [d for d in metadata["distribution"] if d["@type"] == "cr:FileObject"]
    assert ["text/csv", "application/gzip"] in [d.get("encodingFormat") for d in objects]


def test_baker_warnings_survive_markup_in_a_filename(monkeypatch):
    """Show meaningful progress while preserving literal warning filenames."""
    from io import StringIO

    from rich.console import Console

    from biotope.commands.add import _bake_progress

    monkeypatch.setenv("TERM", "xterm-256color")
    output = StringIO()
    monkeypatch.setattr("biotope.commands.add.Console", lambda: Console(file=output, force_terminal=True, width=140))
    with _bake_progress("t") as report:
        report(1, 2, "report.csv")
        logging.getLogger("croissant_baker").warning("report[/].csv: [dim]failed")

    from rich.text import Text

    text = Text.from_ansi(output.getvalue()).plain
    assert "report[/].csv: [dim]failed" in text
    assert "count pending" in output.getvalue()
    assert "1/2" in text
    assert "None" not in output.getvalue()


@pytest.mark.parametrize("input_kind", ["directory", "single_file"])
def test_baker_setup_is_visible_before_import_and_handler_initialization(tmp_path, monkeypatch, capsys, input_kind):
    import builtins

    from croissant_baker import metadata_generator
    from rich.console import Console

    from biotope.commands.add import _enrich_with_baker

    source_dir = tmp_path / "raw"
    source_dir.mkdir()
    source = source_dir / "genes.csv"
    source.write_text("gene_id,score\nG1,2.5\n")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setattr("biotope.commands.add.Console", lambda: Console(force_terminal=True, width=160))
    original_import = builtins.__import__
    original_generator = metadata_generator.MetadataGenerator
    output = ""
    stages = []

    def assert_visible(stage):
        nonlocal output
        output += capsys.readouterr().out
        assert "preparing croissant-baker" in output, stage
        assert "count pending" in output, stage
        stages.append(stage)

    def checked_import(name, *args, **kwargs):
        if name == "croissant_baker.metadata_generator":
            assert_visible("import")
        return original_import(name, *args, **kwargs)

    def checked_generator(*args, **kwargs):
        assert_visible("handler initialization")
        return original_generator(*args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", checked_import)
    monkeypatch.setattr(metadata_generator, "MetadataGenerator", checked_generator)
    if input_kind == "directory":
        metadata, count = _bake_directory(source_dir, tmp_path)
        assert count == 1
    else:
        metadata = {"name": "genes", "distribution": []}
        _enrich_with_baker(metadata, source)
    assert stages == ["import", "handler initialization"]
    assert [f["name"] for f in metadata["recordSet"][0]["field"]] == ["gene_id", "score"]
