"""Human layout and parseable add reports use the same real scan outcomes."""

import json
import logging
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner
from rich.console import Console

from biotope.cli import cli


def test_add_json_covers_files_warnings_outputs_and_rejection(tmp_path, monkeypatch):
    from croissant_baker.metadata_generator import MetadataGenerator

    monkeypatch.chdir(tmp_path)
    runner = CliRunner(mix_stderr=False)
    assert runner.invoke(cli, ["init", ".", "--no-git", "--no-prompt"]).exit_code == 0
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "genes.csv").write_text("id,name\n1,A\n")
    (raw / "notes.txt").write_text("notes")
    (raw / "bad.soft").write_text("not GEO")
    original = MetadataGenerator.generate_metadata

    def noisy(self, *args, **kwargs):
        print("Upstream diagnostic on stdout")
        logging.getLogger("croissant_baker").warning("A diagnostic with [literal] markup")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(MetadataGenerator, "generate_metadata", noisy)
    result = runner.invoke(cli, ["add", "raw", "--json"])
    assert result.exit_code == 0, (result.stdout, result.stderr, result.exception)
    report = json.loads(result.stdout)
    assert report["schema_version"] == 1
    assert report["status"] == "complete_with_gaps"
    source = report["sources"][0]
    assert source["input"] == source["root"] == "raw"
    assert source["manifest"] == ".biotope/datasets/raw.jsonld"
    assert source["annotation_template"] == "raw/.biotope.yaml"
    assert Path(source["manifest"]).is_file()
    files = {f["path"]: f for f in source["scan"]["files"]}
    assert files["genes.csv"]["outcome"] == "described"
    assert files["notes.txt"]["reason"] == "no_handler"
    assert files["bad.soft"]["reason"] == "extract_failed"
    assert files["bad.soft"]["detail"]
    assert source["scan"]["total"] == 3
    assert any(d["message"] == "A diagnostic with [literal] markup" for d in source["diagnostics"])
    assert "Upstream diagnostic on stdout" in result.stderr
    assert "\x1b" not in result.stdout

    skipped = runner.invoke(cli, ["add", "raw", "--json"])
    assert json.loads(skipped.stdout)["sources"][0]["status"] == "skipped"
    (tmp_path / "authored.jsonld").write_text(Path(source["manifest"]).read_text())
    registered = runner.invoke(
        cli, ["source", "register", "authored.jsonld", "--name", "raw", "--reason", "Reviewed", "--replace"]
    )
    assert registered.exit_code == 0, registered.output
    rejected = runner.invoke(cli, ["add", "raw", "--rebake", "--json"])
    assert rejected.exit_code != 0
    failure = json.loads(rejected.stdout)
    assert failure["status"] == "failed"
    assert "curated" in failure["error"]


def test_scan_layout_wraps_long_paths_and_keeps_grouped_members():
    from croissant_baker.scan import Reason, ScanEntry, ScanReport

    from biotope.commands._add_output import AddOutput

    stream = StringIO()
    output = AddOutput(console=Console(file=stream, width=64, color_system=None))
    paths = [f"association_overall_direct/part-{i:05}-aaa1c63d-a07c-4486-af49-c000.snappy.parquet" for i in range(2)]
    failed = "other/part-00000-aaa1c63d-a07c-4486-af49-f58da5ca71d5-c000.snappy.parquet"
    scan = {
        "total": 3,
        "described": 2,
        "linked": 0,
        "referenced": 0,
        "undescribed": 1,
        "by_reason": {"extract_failed": 1},
        "files": [
            *[{"path": p, "outcome": "described"} for p in paths],
            {"path": failed, "outcome": "failed", "reason": "extract_failed", "detail": "Invalid Parquet footer."},
        ],
    }
    with output.scan(Path("raw"), Path("raw")) as progress:
        entry = ScanEntry(Path(failed))
        entry.failed(Reason.EXTRACT_FAILED, ValueError("Invalid Parquet footer."))
        progress.attach(SimpleNamespace(scan_report=ScanReport([entry])))
        progress(1, 3, failed)
        assert "Invalid Parquet footer." in stream.getvalue()  # Visible before assembly finishes.
        progress.finish(scan)
    rendered = stream.getvalue()
    assert "association_overall_direct/ (2 Parquet files)" in rendered
    assert "FAIL   other/" in rendered
    assert "Extraction failed: Invalid Parquet footer." in rendered
    assert all(len(line) <= 64 for line in rendered.splitlines())
    lines = rendered.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("FAIL"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("OK"))
    assert all(line.startswith("       ") for line in lines[start + 1 : end])
    path_lines = []
    for line in lines[start:end]:
        if "Extraction failed" in line:
            break
        path_lines.append(line[7:].strip())
    assert "".join(path_lines) == failed
    assert rendered.count("Invalid Parquet footer.") == 1
    assert output.sources[0]["scan"]["files"] == scan["files"]
