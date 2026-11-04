"""Tests for the add command."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from click.testing import CliRunner

from biotope.cli import cli
from biotope.commands._add_output import AddOutput
from biotope.commands.add import _bake_directory, add
from biotope.graph.inventory import generate_source_packages


@pytest.fixture
def runner():
    return CliRunner()


def test_resolve_dataset_ref_accepts_three_forms(tmp_path):
    """Canonical id, data-path, and manifest-path all resolve to the rel id."""
    from biotope.commands.add import resolve_dataset_ref

    project = tmp_path / "proj"
    datasets_dir = project / ".biotope" / "datasets" / "data" / "inputs"
    datasets_dir.mkdir(parents=True)

    data_file = project / "data" / "inputs" / "kidney.pdf"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text("pdf")

    manifest = datasets_dir / "kidney.pdf.jsonld"
    manifest.write_text("{}")

    canonical = "data/inputs/kidney.pdf"
    assert resolve_dataset_ref(canonical, project) == canonical
    assert resolve_dataset_ref(str(data_file), project) == canonical
    assert resolve_dataset_ref(str(manifest), project) == canonical


def _write_png(path: Path, colour: str = "black") -> None:
    """A 1x1 PNG, so the image handler claims it and emits a FileSet."""
    from PIL import Image

    Image.new("RGB", (1, 1), colour).save(path)


def test_byte_identical_files_are_registered_once_and_never_parsed(tmp_path, capsys):
    project_root = tmp_path / "project"
    data_dir = project_root / "data"
    (project_root / ".biotope" / "datasets").mkdir(parents=True)
    for folder in ("b", "a"):
        (data_dir / folder).mkdir(parents=True)
        (data_dir / folder / "codes.txt").write_text("code\tlabel\n")
        (data_dir / folder / "table.csv").write_text("id,value\n1,x\n2,y\n")
        _write_png(data_dir / folder / "pixel.png")
    (data_dir / "x/b").mkdir(parents=True)
    (data_dir / "x/b/table.csv").write_text("id,value\n3,z\n")

    reporter = AddOutput()
    metadata_dict, _ = _bake_directory(data_dir, project_root, reporter=reporter)

    [source] = reporter.sources
    assert source["duplicates"] == [
        {"path": f"data/b/{name}", "duplicate_of": f"data/a/{name}"} for name in ("codes.txt", "pixel.png", "table.csv")
    ]
    assert sorted(file["path"] for file in source["scan"]["files"]) == [
        "a/codes.txt",
        "a/pixel.png",
        "a/table.csv",
        "x/b/table.csv",
    ]
    assert source["diagnostics"] == []
    assert "x/b/table.csv#table" in {record["@id"] for record in metadata_dict["recordSet"]}
    urls = {item["@type"]: [] for item in metadata_dict["distribution"]}
    for item in metadata_dict["distribution"]:
        urls[item["@type"]].append(item.get("contentUrl") or item.get("excludes"))
    assert sorted(urls["cr:FileObject"]) == ["a/codes.txt", "a/pixel.png", "a/table.csv", "x/b/table.csv"]
    assert urls["cr:FileSet"] == [["b/pixel.png"]]
    generate_source_packages(project_root / ".biotope/datasets/data.jsonld", project_root / "graph/sources")

    text = " ".join(capsys.readouterr().err.split())
    assert "SKIP b/table.csv Identical to a/table.csv; registered once" in text
    assert "OK b/" not in text
    assert "4 scanned · 3 described · 1 not described · 3 identical" in text
    assert text.index("Identical to a/table.csv") < text.index("4 scanned")


def _project(tmp_path, monkeypatch):
    created = CliRunner().invoke(cli, ["init", "study", "--dir", str(tmp_path), "--no-prompt"])
    assert created.exit_code == 0, created.output
    root = tmp_path / "study"
    monkeypatch.chdir(root)
    return root


def _add(*args):
    result = CliRunner(mix_stderr=False).invoke(cli, ["add", *args, "--json"])
    return result, json.loads(result.stdout)


def test_add_refuses_a_dataset_that_overlaps_another(tmp_path, monkeypatch):
    root = _project(tmp_path, monkeypatch)
    (root / "data/pages").mkdir(parents=True)
    (root / "data/pages/a.html").write_text("<h1>A</h1>")
    (root / "data/people.csv").write_text("id\n1\n")
    (root / "data/new").mkdir()
    (root / "data/new/b.csv").write_text("id\n2\n")
    assert _add("data/pages", "data/people.csv")[0].exit_code == 0
    described = {path: path.read_bytes() for path in (root / ".biotope/datasets").rglob("*.jsonld")}

    around, around_report = _add("--rebake", "data")
    inside, inside_report = _add("data/pages/a.html")
    together, together_report = _add("data/new", "data/new/b.csv")

    assert around.exit_code != 0 and inside.exit_code != 0 and together.exit_code != 0
    assert around_report["error"].startswith("data overlaps the datasets data/pages, data/people.csv. ")
    assert "A file belongs to one dataset" in around_report["error"]
    assert inside_report["error"].startswith("data/pages/a.html overlaps the dataset data/pages. ")
    assert together_report["error"].startswith(
        "data/new overlaps the dataset data/new/b.csv; data/new/b.csv overlaps the dataset data/new. "
    )
    assert {path: path.read_bytes() for path in (root / ".biotope/datasets").rglob("*.jsonld")} == described
    assert _add("--rebake", "data/pages")[0].exit_code == 0


def test_add_names_the_columns_and_annotation_files_it_leaves_out(tmp_path, monkeypatch):
    root = _project(tmp_path, monkeypatch)
    (root / "data/papers").mkdir(parents=True)
    (root / "data/signature.csv").write_text("gene,L2FC,FDR,L2FC,FDR,note\nA,1,0.1,2,0.2,x\n")
    (root / "data/papers/.biotope.yaml").write_text("dataset: {}\n")
    (root / "data/signature.csv.biotope.yaml").write_text("description: old\n")

    result, report = _add("data")

    assert result.exit_code == 0, result.output
    [source] = report["sources"]
    messages = [diagnostic["message"] for diagnostic in source["diagnostics"]]
    assert messages == [
        "data/signature.csv repeats the columns FDR, L2FC; the description keeps the first column of each name, "
        "so read the others in the file's source package",
        "data/papers/.biotope.yaml belongs to no dataset, so biotope ignores it; "
        "this dataset's annotation file is data/.biotope.yaml",
        "data/signature.csv.biotope.yaml belongs to no dataset, so biotope ignores it; "
        "this dataset's annotation file is data/.biotope.yaml",
    ]


def test_add_command_rejects_name_for_multiple_paths(runner, tmp_path):
    file_one = tmp_path / "one.txt"
    file_two = tmp_path / "two.txt"
    file_one.write_text("one")
    file_two.write_text("two")

    result = runner.invoke(add, ["--name", "dataset", str(file_one), str(file_two)])

    assert result.exit_code != 0
    assert "--name can only be used when adding one path" in result.output


def test_baker_warnings_survive_markup_in_a_filename(monkeypatch):
    """Show meaningful progress while preserving literal warning filenames."""
    from io import StringIO

    from rich.console import Console

    from biotope.commands._add_output import AddOutput

    monkeypatch.setenv("TERM", "xterm-256color")
    output = StringIO()
    presenter = AddOutput(console=Console(file=output, force_terminal=True, width=140))
    with presenter.scan(Path("t"), Path("t")) as report:
        report(1, 2, "report.csv")
        logging.getLogger("croissant_baker").warning("report[/].csv: [dim]failed")

    from rich.text import Text

    text = Text.from_ansi(output.getvalue()).plain
    assert "report[/].csv: [dim]failed" in text
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
    monkeypatch.setattr(
        "biotope.commands._add_output.Console", lambda **kwargs: Console(force_terminal=True, width=160, **kwargs)
    )
    original_import = builtins.__import__
    original_generator = metadata_generator.MetadataGenerator
    output = ""
    stages = []

    def assert_visible(stage):
        nonlocal output
        captured = capsys.readouterr()
        output += captured.err
        assert "Baking" in output, stage
        assert "preparing croissant-baker" not in captured.out + output, stage
        assert "\x1b[?25l" in output, stage  # The live display already hides the cursor.
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
    captured = capsys.readouterr()
    assert "\x1b[?25h" in captured.err  # Progress has restored the terminal.
    assert captured.out == ""
    assert "1 scanned · 1 described" in captured.err
    assert [f["name"] for f in metadata["recordSet"][0]["field"]] == ["gene_id", "score"]
