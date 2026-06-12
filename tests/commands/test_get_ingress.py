"""Tests for the generalised `biotope get` ingress verb (issue #22).

Covers local file/directory copy-and-bake, the website-scrape path, source
provenance stamping, and the dispatch guards. The pre-existing URL-download
behaviour is covered by tests/commands/test_get.py.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.get import get
from biotope.metadata import FETCHED_AT_KEY, SOURCE_KEY
from biotope.scrape import ScrapeResult, ScrapedPage


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def biotope_project(tmp_path: Path) -> Path:
    """A real git-backed biotope project at <tmp>/project."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    biotope_dir = project_dir / ".biotope"
    (biotope_dir / "datasets").mkdir(parents=True)
    (biotope_dir / "config.yaml").write_text("project_name: test_project\n")
    subprocess.run(["git", "init"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_dir, check=True)
    return project_dir


@pytest.fixture
def external_file(tmp_path: Path) -> Path:
    """A CSV file living *outside* the project tree."""
    src = tmp_path / "external" / "genes.csv"
    src.parent.mkdir(parents=True)
    src.write_text("GeneID,Expression\nBRCA1,12.5\nTP53,8.7\n")
    return src


@pytest.fixture
def external_dir(tmp_path: Path) -> Path:
    """A directory of files living *outside* the project tree."""
    root = tmp_path / "external" / "source_pull"
    (root / "sub").mkdir(parents=True)
    (root / "a.csv").write_text("col1,col2\n1,2\n3,4\n")
    (root / "sub" / "b.csv").write_text("x,y\n5,6\n")
    return root


def _invoke(runner: CliRunner, biotope_project: Path, args: list[str]):
    """Run `get` with the project root resolved (cwd-independent)."""
    with mock.patch("biotope.commands.get.find_biotope_root", return_value=biotope_project):
        return runner.invoke(get, args)


def _only_manifest(biotope_project: Path) -> dict:
    manifests = list((biotope_project / ".biotope" / "datasets").rglob("*.jsonld"))
    assert len(manifests) == 1, manifests
    return json.loads(manifests[0].read_text())


# --------------------------------------------------------------------------- #
# Local file
# --------------------------------------------------------------------------- #


def test_get_local_file_copies_and_bakes(runner, biotope_project, external_file):
    result = _invoke(runner, biotope_project, [str(external_file)])
    assert result.exit_code == 0, result.output

    copied = biotope_project / "data" / "genes.csv"
    assert copied.exists()
    assert copied.read_text() == external_file.read_text()

    metadata = _only_manifest(biotope_project)
    assert metadata[SOURCE_KEY] == str(external_file.resolve())
    assert FETCHED_AT_KEY in metadata
    assert metadata["distribution"][0]["name"] == "genes.csv"


def test_get_local_file_status_override(runner, biotope_project, external_file):
    result = _invoke(runner, biotope_project, [str(external_file), "--status", "raw"])
    assert result.exit_code == 0, result.output
    assert _only_manifest(biotope_project)["biotope:status"] == "raw"


def test_get_local_file_no_add(runner, biotope_project, external_file):
    result = _invoke(runner, biotope_project, [str(external_file), "--no-add"])
    assert result.exit_code == 0, result.output
    assert (biotope_project / "data" / "genes.csv").exists()
    assert not list((biotope_project / ".biotope" / "datasets").rglob("*.jsonld"))
    assert "To add to biotope project" in result.output


def test_get_local_file_custom_into(runner, biotope_project, external_file):
    result = _invoke(runner, biotope_project, [str(external_file), "--into", "data/raw"])
    assert result.exit_code == 0, result.output
    assert (biotope_project / "data" / "raw" / "genes.csv").exists()


def test_get_local_file_output_dir_alias(runner, biotope_project, external_file):
    """The legacy --output-dir flag still routes to --into."""
    result = _invoke(runner, biotope_project, [str(external_file), "--output-dir", "inputs"])
    assert result.exit_code == 0, result.output
    assert (biotope_project / "inputs" / "genes.csv").exists()


def test_get_local_file_metadata_overrides(runner, biotope_project, external_file):
    result = _invoke(
        runner,
        biotope_project,
        [str(external_file), "--license", "CC-BY-4.0", "--creator", "Source Org"],
    )
    assert result.exit_code == 0, result.output
    metadata = _only_manifest(biotope_project)
    assert metadata["license"] == "CC-BY-4.0"
    assert metadata["creator"]["name"] == "Source Org"


# --------------------------------------------------------------------------- #
# Local directory
# --------------------------------------------------------------------------- #


def test_get_local_dir_copies_and_bakes(runner, biotope_project, external_dir):
    result = _invoke(runner, biotope_project, [str(external_dir)])
    assert result.exit_code == 0, result.output

    assert (biotope_project / "data" / "source_pull" / "a.csv").exists()
    assert (biotope_project / "data" / "source_pull" / "sub" / "b.csv").exists()
    # A directory ingest writes one composite manifest + a review scaffold.
    assert (biotope_project / "data" / "source_pull" / ".biotope.yaml").exists()

    manifest = biotope_project / ".biotope" / "datasets" / "data" / "source_pull.jsonld"
    assert manifest.exists()
    metadata = json.loads(manifest.read_text())
    assert metadata[SOURCE_KEY] == str(external_dir.resolve())
    assert FETCHED_AT_KEY in metadata


def test_get_local_dir_no_add(runner, biotope_project, external_dir):
    result = _invoke(runner, biotope_project, [str(external_dir), "--no-add"])
    assert result.exit_code == 0, result.output
    assert (biotope_project / "data" / "source_pull" / "a.csv").exists()
    assert not list((biotope_project / ".biotope" / "datasets").rglob("*.jsonld"))


# --------------------------------------------------------------------------- #
# Dispatch guards
# --------------------------------------------------------------------------- #


def test_get_unsupported_scheme_aborts(runner, biotope_project):
    result = _invoke(runner, biotope_project, ["s3://bucket/key.csv"])
    assert result.exit_code != 0
    assert "Unsupported source" in result.output


def test_get_crawl_requires_http(runner, biotope_project, external_file):
    result = _invoke(runner, biotope_project, [str(external_file), "--crawl"])
    assert result.exit_code != 0
    assert "--crawl requires an http(s) URL" in result.output


def test_get_source_not_found_aborts(runner, biotope_project, tmp_path):
    missing = tmp_path / "nope.csv"
    result = _invoke(runner, biotope_project, [str(missing)])
    assert result.exit_code != 0
    assert "Source not found" in result.output


def test_get_source_already_in_project_aborts(runner, biotope_project):
    inside = biotope_project / "data" / "already.csv"
    inside.parent.mkdir(parents=True)
    inside.write_text("a,b\n1,2\n")
    result = _invoke(runner, biotope_project, [str(inside)])
    assert result.exit_code != 0
    assert "already inside the project" in result.output
    assert "biotope add" in result.output


# --------------------------------------------------------------------------- #
# Website scrape
# --------------------------------------------------------------------------- #


def _fake_crawl_two_pages(seed_url: str, dest_dir: Path, **_kwargs) -> ScrapeResult:
    """Stand in for scrape.crawl: write two HTML pages, report them."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "index.html").write_text("<html>home</html>")
    (dest_dir / "topic").mkdir(exist_ok=True)
    (dest_dir / "topic" / "a.html").write_text("<html>a</html>")
    return ScrapeResult(
        host="example.com",
        pages=[
            ScrapedPage(url="https://example.com/", relpath=Path("index.html")),
            ScrapedPage(url="https://example.com/topic/a", relpath=Path("topic/a.html")),
        ],
        skipped=[("https://example.com/blocked", "blocked by robots.txt")],
    )


def test_get_scrape_bakes_manifest_with_per_page_source(runner, biotope_project):
    with mock.patch("biotope.commands.get.crawl", side_effect=_fake_crawl_two_pages):
        result = _invoke(
            runner,
            biotope_project,
            ["https://example.com/", "--crawl", "--depth", "1"],
        )
    assert result.exit_code == 0, result.output

    manifest = biotope_project / ".biotope" / "datasets" / "data" / "example.com.jsonld"
    assert manifest.exists()
    metadata = json.loads(manifest.read_text())

    # Dataset-level provenance points at the seed; status defaults to raw (HTML).
    assert metadata[SOURCE_KEY] == "https://example.com/"
    assert metadata["biotope:status"] == "raw"

    # Each page carries its own source URL inline.
    by_url = {d[SOURCE_KEY] for d in metadata["distribution"]}
    assert by_url == {"https://example.com/", "https://example.com/topic/a"}


def test_get_scrape_no_add(runner, biotope_project):
    with mock.patch("biotope.commands.get.crawl", side_effect=_fake_crawl_two_pages):
        result = _invoke(
            runner,
            biotope_project,
            ["https://example.com/", "--crawl", "--no-add"],
        )
    assert result.exit_code == 0, result.output
    assert (biotope_project / "data" / "example.com" / "index.html").exists()
    assert not list((biotope_project / ".biotope" / "datasets").rglob("*.jsonld"))


def test_get_scrape_no_pages_aborts(runner, biotope_project):
    def _empty_crawl(seed_url, dest_dir, **_kwargs):
        return ScrapeResult(host="example.com", pages=[], skipped=[("https://example.com/x", "fetch error: boom")])

    with mock.patch("biotope.commands.get.crawl", side_effect=_empty_crawl):
        result = _invoke(runner, biotope_project, ["https://example.com/", "--crawl"])
    assert result.exit_code != 0
    assert "No pages saved" in result.output


def test_get_scrape_status_override(runner, biotope_project):
    with mock.patch("biotope.commands.get.crawl", side_effect=_fake_crawl_two_pages):
        result = _invoke(runner, biotope_project, ["https://example.com/", "--crawl", "--status", "processed"])
    assert result.exit_code == 0, result.output
    manifest = biotope_project / ".biotope" / "datasets" / "data" / "example.com.jsonld"
    assert json.loads(manifest.read_text())["biotope:status"] == "processed"


def test_scrape_dataset_addressable_by_ref(runner, biotope_project):
    """The dotted-host dataset must resolve via mark/derived-from style refs."""
    from biotope.commands.add import _resolve_dataset_ref

    with mock.patch("biotope.commands.get.crawl", side_effect=_fake_crawl_two_pages):
        _invoke(runner, biotope_project, ["https://example.com/", "--crawl"])

    # Bare canonical id and the data-path form (the with_suffix bug) both resolve.
    assert _resolve_dataset_ref("data/example.com", biotope_project) == "data/example.com"
    assert _resolve_dataset_ref(str(biotope_project / "data" / "example.com"), biotope_project) == "data/example.com"


# --------------------------------------------------------------------------- #
# Provenance + containment + autoinit
# --------------------------------------------------------------------------- #


def test_get_derived_from_records_provenance(runner, biotope_project, external_file, tmp_path):
    base = tmp_path / "ext_base" / "base.csv"
    base.parent.mkdir(parents=True)
    base.write_text("a,b\n1,2\n")
    _invoke(runner, biotope_project, [str(base)])  # → data/base.csv, id "data/base"

    result = _invoke(runner, biotope_project, [str(external_file), "--derived-from", "data/base"])
    assert result.exit_code == 0, result.output
    metadata = json.loads((biotope_project / ".biotope" / "datasets" / "data" / "genes.jsonld").read_text())
    assert any(entry.get("@id") == "data/base" for entry in metadata["prov:wasDerivedFrom"])


def test_get_derived_from_bad_ref_aborts(runner, biotope_project, external_file):
    result = _invoke(runner, biotope_project, [str(external_file), "--derived-from", "does/not/exist"])
    assert result.exit_code != 0


def test_get_into_absolute_rejected(runner, biotope_project, external_file):
    result = _invoke(runner, biotope_project, [str(external_file), "--into", "/tmp/escape"])
    assert result.exit_code != 0
    assert "--into" in result.output


def test_get_into_traversal_rejected(runner, biotope_project, external_file):
    result = _invoke(runner, biotope_project, [str(external_file), "--into", "../escape"])
    assert result.exit_code != 0


def test_get_local_file_via_file_url(runner, biotope_project, external_file):
    url = "file://" + str(external_file.resolve())
    result = _invoke(runner, biotope_project, [url])
    assert result.exit_code == 0, result.output
    assert (biotope_project / "data" / "genes.csv").exists()
    assert _only_manifest(biotope_project)[SOURCE_KEY] == str(external_file.resolve())


def test_get_local_dir_skips_symlinks(runner, biotope_project, tmp_path):
    src = tmp_path / "ext_pull" / "pull"
    src.mkdir(parents=True)
    (src / "real.csv").write_text("a,b\n1,2\n")
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    (src / "link.txt").symlink_to(secret)

    result = _invoke(runner, biotope_project, [str(src)])
    assert result.exit_code == 0, result.output
    assert (biotope_project / "data" / "pull" / "real.csv").exists()
    # The symlink (and its external target's content) must not be copied in.
    assert not (biotope_project / "data" / "pull" / "link.txt").exists()
    assert "symlink" in result.output.lower()


def test_get_autoinit_with_local_source(runner, tmp_path):
    """Outside a project, get scaffolds one and lands a local file at the new root."""
    ext = tmp_path / "ext_auto" / "genes.csv"
    ext.parent.mkdir(parents=True)
    ext.write_text("GeneID,Expression\nBRCA1,12.5\n")

    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(get, [str(ext)])
        assert result.exit_code == 0, result.output
        assert Path("data/.biotope").is_dir()
        # autoinit lands data at the new root (not under data/data/).
        assert Path("data/genes.csv").exists()
        manifests = list(Path("data/.biotope/datasets").rglob("*.jsonld"))
        assert len(manifests) == 1
        assert json.loads(manifests[0].read_text())[SOURCE_KEY] == str(ext.resolve())
