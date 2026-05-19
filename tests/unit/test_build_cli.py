"""End-to-end CLI walkthrough: init -> describe -> propose-mapping -> build."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from biotope.commands.build import build
from biotope.commands.describe import describe
from biotope.commands.init import init
from biotope.commands.propose_mapping import propose_mapping

FIXTURES = Path(__file__).parent.parent / "fixtures" / "croissant"


def test_full_walkthrough(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()

    # 1. init
    r = runner.invoke(init, ["bcc-e2e", "--dir", str(tmp_path), "--no-git"])
    assert r.exit_code == 0, r.output
    project_dir = tmp_path / "bcc-e2e"
    monkeypatch.chdir(project_dir)

    # 2. describe
    r = runner.invoke(describe, ["--purpose", "Walkthrough test", "--entity", "genes"])
    assert r.exit_code == 0, r.output

    # 3. propose-mapping against the minimal Croissant fixture
    minimal = FIXTURES / "minimal.croissant.json"
    out_mapping = project_dir / "mappings" / "minimal.mapping.yaml"
    r = runner.invoke(
        propose_mapping,
        [str(minimal), "--out", str(out_mapping)],
    )
    assert r.exit_code == 0, r.output
    assert out_mapping.is_file()

    # 4. build
    r = runner.invoke(build, [])
    assert r.exit_code == 0, r.output
    build_dir = project_dir / "build"
    assert (build_dir / "config" / "schema_config.yaml").is_file()
    assert (build_dir / "config" / "biocypher_config.yaml").is_file()
    assert (build_dir / "create_knowledge_graph.py").is_file()
    assert (build_dir / "mappings" / "minimal.mapping.yaml").is_file()

    # build emits a JSON report somewhere in stdout
    assert "project_dir" in r.output
    assert "schema_config" in r.output
