"""Tests for `biotope mv` against multi-file manifests and whole-dataset renames."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from biotope.commands.mv import mv


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".biotope" / "datasets").mkdir(parents=True)
    return tmp_path


def _write_manifest(project_dir: Path, rel_id: str, distribution: list[dict]) -> Path:
    manifest_path = project_dir / ".biotope" / "datasets" / f"{rel_id}.jsonld"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "@type": "sc:Dataset",
                "name": rel_id,
                "distribution": distribution,
            }
        )
    )
    return manifest_path


def test_fileset_rename_pattern_still_matches(runner: CliRunner, project: Path) -> None:
    """Renaming a FileSet-covered file to a name that still matches the
    glob succeeds with no manifest update."""
    data_dir = project / "data" / "ot"
    data_dir.mkdir(parents=True)
    src = data_dir / "part-00.parquet"
    src.write_bytes(b"x")

    _write_manifest(
        project,
        "data/ot",
        distribution=[
            {"@type": "cr:FileSet", "@id": "fs", "includes": "*.parquet"},
        ],
    )

    dst = data_dir / "part-renamed.parquet"
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


def test_fileset_rename_pattern_no_longer_matches_refused(runner: CliRunner, project: Path) -> None:
    """Renaming a FileSet-covered file to a name that DOESN'T match the
    glob is refused — would leave the manifest stale."""
    data_dir = project / "data" / "ot"
    data_dir.mkdir(parents=True)
    src = data_dir / "part-00.parquet"
    src.write_bytes(b"x")

    _write_manifest(
        project,
        "data/ot",
        distribution=[
            {"@type": "cr:FileSet", "@id": "fs", "includes": "*.parquet"},
        ],
    )

    dst = data_dir / "renamed.txt"
    import os

    os.chdir(project)
    r = runner.invoke(mv, [str(src), str(dst)])
    assert r.exit_code != 0
    assert "FileSet" in r.output
    assert src.exists()
    assert not dst.exists()
