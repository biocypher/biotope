"""Tests for `biotope mv` against multi-file manifests and whole-dataset renames."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.mv import mv


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".biotope" / "datasets").mkdir(parents=True)
    (tmp_path / ".git").mkdir()
    return tmp_path


def _write_manifest(project_dir: Path, rel_id: str, distribution: list[dict]) -> Path:
    manifest_path = project_dir / ".biotope" / "datasets" / f"{rel_id}.jsonld"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({
        "@type": "sc:Dataset",
        "name": rel_id,
        "distribution": distribution,
    }))
    return manifest_path


# ---------------------------------------------------------------------------
# Whole-dataset rename
# ---------------------------------------------------------------------------


def test_whole_dataset_rename_moves_data_and_manifest(
    runner: CliRunner, project: Path
) -> None:
    """`biotope mv data/raw/ot data/processed/ot` is the primary multi-file
    case: data dir moves, manifest renames to mirror, contentUrls and the
    `name` field are rewritten."""
    data_dir = project / "data" / "raw" / "ot"
    data_dir.mkdir(parents=True)
    (data_dir / "README.md").write_text("notes")
    (data_dir / "part-00.parquet").write_bytes(b"x")

    _write_manifest(project, "data/raw/ot", distribution=[
        {"@type": "cr:FileSet", "@id": "fs", "includes": "*.parquet"},
        {"@type": "cr:FileObject", "@id": "fo", "contentUrl": "data/raw/ot/README.md",
         "sha256": "abc", "contentSize": "5"},
    ])

    with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
        with mock.patch("biotope.commands.mv.stage_git_changes"):
            import os
            os.chdir(project)
            r = runner.invoke(mv, [
                str(data_dir),
                str(project / "data" / "processed" / "ot"),
                "-r",
            ])
    assert r.exit_code == 0, r.output

    # Data moved.
    assert not data_dir.exists()
    new_dir = project / "data" / "processed" / "ot"
    assert (new_dir / "README.md").exists()
    assert (new_dir / "part-00.parquet").exists()

    # Manifest renamed; old path is gone.
    old_manifest = project / ".biotope" / "datasets" / "data" / "raw" / "ot.jsonld"
    new_manifest = project / ".biotope" / "datasets" / "data" / "processed" / "ot.jsonld"
    assert not old_manifest.exists()
    assert new_manifest.exists()

    # contentUrls and name are rewritten; FileSet `includes` is unchanged
    # (relative to dataset_dir).
    metadata = json.loads(new_manifest.read_text())
    assert metadata["name"] == "data/processed/ot"
    urls = [d["contentUrl"] for d in metadata["distribution"] if d["@type"] == "cr:FileObject"]
    assert urls == ["data/processed/ot/README.md"]
    fileset = next(d for d in metadata["distribution"] if d["@type"] == "cr:FileSet")
    assert fileset["includes"] == "*.parquet"


def test_whole_dataset_rename_carries_nested_manifests(
    runner: CliRunner, project: Path
) -> None:
    """If the user has nested sub-datasets under the moved dir, their
    manifests under .biotope/datasets/<source_rel>/ must move alongside,
    and their contentUrl prefixes must be rewritten."""
    parent = project / "data" / "raw" / "ot"
    parent.mkdir(parents=True)
    sub = parent / "target"
    sub.mkdir()
    (sub / "x.parquet").write_bytes(b"x")

    _write_manifest(project, "data/raw/ot", distribution=[
        {"@type": "cr:FileObject", "@id": "fo_outer",
         "contentUrl": "data/raw/ot/notes.md", "sha256": "abc", "contentSize": "5"},
        {"@type": "cr:FileObject", "@id": "fo_outer2",
         "contentUrl": "data/raw/ot/other.md", "sha256": "abc", "contentSize": "5"},
    ])
    (parent / "notes.md").write_text("notes")
    (parent / "other.md").write_text("other")
    _write_manifest(project, "data/raw/ot/target", distribution=[
        {"@type": "cr:FileSet", "@id": "fs", "includes": "*.parquet"},
    ])

    with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
        with mock.patch("biotope.commands.mv.stage_git_changes"):
            import os
            os.chdir(project)
            r = runner.invoke(mv, [
                str(parent),
                str(project / "data" / "processed" / "ot"),
                "-r",
            ])
    assert r.exit_code == 0, r.output

    # Top-level manifest renamed.
    new_top = project / ".biotope" / "datasets" / "data" / "processed" / "ot.jsonld"
    assert new_top.exists()
    metadata = json.loads(new_top.read_text())
    urls = sorted(d["contentUrl"] for d in metadata["distribution"] if d["@type"] == "cr:FileObject")
    assert urls == ["data/processed/ot/notes.md", "data/processed/ot/other.md"]

    # Nested sub-dataset manifest carried along.
    new_sub = project / ".biotope" / "datasets" / "data" / "processed" / "ot" / "target.jsonld"
    assert new_sub.exists()
    # Old nested path cleaned up.
    old_sub = project / ".biotope" / "datasets" / "data" / "raw" / "ot" / "target.jsonld"
    assert not old_sub.exists()


# ---------------------------------------------------------------------------
# Single file inside a multi-file manifest
# ---------------------------------------------------------------------------


def test_file_object_rename_within_dataset_updates_contentUrl_in_place(
    runner: CliRunner, project: Path
) -> None:
    data_dir = project / "data" / "ot"
    data_dir.mkdir(parents=True)
    src = data_dir / "README.md"
    src.write_text("notes")

    _write_manifest(project, "data/ot", distribution=[
        {"@type": "cr:FileObject", "@id": "f1",
         "contentUrl": "data/ot/README.md", "sha256": "abc", "contentSize": "5"},
        {"@type": "cr:FileObject", "@id": "f2",
         "contentUrl": "data/ot/CHANGELOG.md", "sha256": "abc", "contentSize": "5"},
    ])

    dst = data_dir / "README_v2.md"
    with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
        with mock.patch("biotope.commands.mv.stage_git_changes"):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                import os
                os.chdir(project)
                r = runner.invoke(mv, [str(src), str(dst)])
    assert r.exit_code == 0, r.output

    # File moved.
    assert not src.exists()
    assert dst.exists()

    # Manifest stays in place; contentUrl updated.
    manifest = project / ".biotope" / "datasets" / "data" / "ot.jsonld"
    assert manifest.exists()
    metadata = json.loads(manifest.read_text())
    urls = sorted(d["contentUrl"] for d in metadata["distribution"])
    assert urls == ["data/ot/CHANGELOG.md", "data/ot/README_v2.md"]


def test_file_object_cross_dataset_move_refused(
    runner: CliRunner, project: Path
) -> None:
    """Moving a file out of its dataset_dir would leave the manifest with a
    stray contentUrl outside its own dataset — refuse."""
    src_dir = project / "data" / "ot"
    src_dir.mkdir(parents=True)
    src = src_dir / "README.md"
    src.write_text("notes")

    _write_manifest(project, "data/ot", distribution=[
        {"@type": "cr:FileObject", "@id": "f1",
         "contentUrl": "data/ot/README.md", "sha256": "abc", "contentSize": "5"},
        {"@type": "cr:FileObject", "@id": "f2",
         "contentUrl": "data/ot/other.md", "sha256": "abc", "contentSize": "5"},
    ])

    other_dir = project / "data" / "elsewhere"
    other_dir.mkdir(parents=True)
    dst = other_dir / "README.md"

    with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
        with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
            import os
            os.chdir(project)
            r = runner.invoke(mv, [str(src), str(dst)])
    assert r.exit_code != 0
    assert "Cross-dataset" in r.output
    # Nothing moved.
    assert src.exists()
    assert not dst.exists()


def test_fileset_rename_pattern_still_matches(
    runner: CliRunner, project: Path
) -> None:
    """Renaming a FileSet-covered file to a name that still matches the
    glob succeeds with no manifest update."""
    data_dir = project / "data" / "ot"
    data_dir.mkdir(parents=True)
    src = data_dir / "part-00.parquet"
    src.write_bytes(b"x")

    _write_manifest(project, "data/ot", distribution=[
        {"@type": "cr:FileSet", "@id": "fs", "includes": "*.parquet"},
    ])

    dst = data_dir / "part-renamed.parquet"
    with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
        with mock.patch("biotope.commands.mv.stage_git_changes"):
            with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
                import os
                os.chdir(project)
                r = runner.invoke(mv, [str(src), str(dst)])
    assert r.exit_code == 0, r.output
    assert dst.exists()
    assert not src.exists()
    # Manifest unchanged — FileSet still covers via pattern.
    manifest = project / ".biotope" / "datasets" / "data" / "ot.jsonld"
    metadata = json.loads(manifest.read_text())
    assert metadata["distribution"][0]["includes"] == "*.parquet"


def test_fileset_rename_pattern_no_longer_matches_refused(
    runner: CliRunner, project: Path
) -> None:
    """Renaming a FileSet-covered file to a name that DOESN'T match the
    glob is refused — would leave the manifest stale."""
    data_dir = project / "data" / "ot"
    data_dir.mkdir(parents=True)
    src = data_dir / "part-00.parquet"
    src.write_bytes(b"x")

    _write_manifest(project, "data/ot", distribution=[
        {"@type": "cr:FileSet", "@id": "fs", "includes": "*.parquet"},
    ])

    dst = data_dir / "renamed.txt"
    with mock.patch("biotope.commands.mv.is_git_repo", return_value=True):
        with mock.patch("biotope.commands.mv.is_file_tracked", return_value=True):
            import os
            os.chdir(project)
            r = runner.invoke(mv, [str(src), str(dst)])
    assert r.exit_code != 0
    assert "FileSet" in r.output
    assert src.exists()
    assert not dst.exists()
