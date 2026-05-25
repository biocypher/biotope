"""End-to-end CLI walkthrough on the semantic IR: init -> map flags -> scaffold -> resolve -> build."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from biotope.commands.build import build
from biotope.commands.init import init
from biotope.commands.map import map_group
from biotope.commands.propose_alignment import propose_alignment as propose_alignment_cmd
from biotope.commands.propose_mapping import propose_mapping


FIXTURES = Path(__file__).parent.parent / "fixtures" / "croissant"


def _write_resolved_mapping(project_dir: Path, croissant: Path) -> Path:
    out = project_dir / "mappings" / "minimal.mapping.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(
            {
                "croissant": str(croissant),
                "entities": {
                    "gene": {
                        "record_set": "genes",
                        "id": {
                            "field": "ensembl_id",
                            "transform": "as_curie",
                            "args": {"prefix": "ensembl"},
                        },
                        "properties": {"symbol": "symbol", "biotype": "biotype"},
                    }
                },
            },
            sort_keys=False,
        )
    )
    return out


def test_full_walkthrough(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()

    r = runner.invoke(init, ["bcc-e2e", "--dir", str(tmp_path), "--no-git", "--no-prompt"])
    assert r.exit_code == 0, r.output
    project_dir = tmp_path / "bcc-e2e"
    monkeypatch.chdir(project_dir)

    # Intent capture via `biotope map` non-interactive flags
    r = runner.invoke(map_group, ["--purpose", "Walkthrough test", "--entity", "gene"])
    assert r.exit_code == 0, r.output

    minimal = FIXTURES / "minimal.croissant.json"
    r = runner.invoke(map_group, ["scaffold", str(minimal)])
    assert r.exit_code == 0, r.output
    out_mapping = project_dir / "mappings" / "minimal.mapping.yaml"
    assert out_mapping.is_file()
    mapping_text = out_mapping.read_text()
    assert "# Croissant inspection appendix" in mapping_text

    # Replace the unresolved scaffold with a fully resolved mapping for build
    _write_resolved_mapping(project_dir, minimal)

    r = runner.invoke(build, [])
    assert r.exit_code == 0, r.output
    build_dir = project_dir / "build"
    assert (build_dir / "config" / "schema_config.yaml").is_file()
    assert (build_dir / "generated" / "minimal" / "adapter.py").is_file()
    assert "project_dir" in r.output
    # Headless contract: the generated biocypher_config opts out of Biolink.
    bc_cfg = yaml.safe_load((build_dir / "config" / "biocypher_config.yaml").read_text())
    assert bc_cfg["biocypher"]["head_ontology"] is None


def test_build_rejects_unresolved_mapping(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    r = runner.invoke(init, ["bcc-e2e", "--dir", str(tmp_path), "--no-git", "--no-prompt"])
    assert r.exit_code == 0, r.output
    project_dir = tmp_path / "bcc-e2e"
    monkeypatch.chdir(project_dir)

    runner.invoke(map_group, ["--entity", "gene"])
    minimal = FIXTURES / "minimal.croissant.json"
    r = runner.invoke(map_group, ["scaffold", str(minimal)])
    assert r.exit_code == 0, r.output

    r = runner.invoke(build, [])
    assert r.exit_code != 0
    # `gene` was declared in intent but never bound in any mapping — the
    # project-wide coverage check should call that out, not just "unresolved".
    assert "not bound in any mapping" in r.output
    assert "gene" in r.output


def test_propose_mapping_deprecated_alias_still_works(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    r = runner.invoke(init, ["bcc-e2e", "--dir", str(tmp_path), "--no-git", "--no-prompt"])
    assert r.exit_code == 0, r.output
    project_dir = tmp_path / "bcc-e2e"
    monkeypatch.chdir(project_dir)

    minimal = FIXTURES / "minimal.croissant.json"
    r = runner.invoke(propose_mapping, [str(minimal)])
    assert r.exit_code == 0, r.output
    assert "deprecated" in r.output.lower()
    assert (project_dir / "mappings" / "minimal.mapping.yaml").is_file()


def test_propose_alignment_defaults_to_project_alignment_yaml(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()

    r = runner.invoke(init, ["bcc-e2e", "--dir", str(tmp_path), "--no-git", "--no-prompt"])
    assert r.exit_code == 0, r.output
    project_dir = tmp_path / "bcc-e2e"
    monkeypatch.chdir(project_dir)

    runner.invoke(map_group, ["--entity", "gene"])

    minimal = FIXTURES / "minimal.croissant.json"
    a = project_dir / "mappings" / "a.mapping.yaml"
    b = project_dir / "mappings" / "b.mapping.yaml"
    for target in (a, b):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(
                {
                    "croissant": str(minimal),
                    "entities": {
                        "gene": {
                            "record_set": "genes",
                            "id": "ensembl_id",
                            "properties": {"symbol": "symbol"},
                        }
                    },
                }
            )
        )

    r = runner.invoke(propose_alignment_cmd, [str(a), str(b)])
    assert r.exit_code == 0, r.output

    alignment_path = project_dir / "alignment.yaml"
    assert alignment_path.is_file()
    alignment_text = alignment_path.read_text()
    assert "equivalences:" in alignment_text
    assert "kind: same_node" in alignment_text


def test_map_intent_flags_update_project(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    r = runner.invoke(init, ["bcc-e2e", "--dir", str(tmp_path), "--no-git", "--no-prompt"])
    assert r.exit_code == 0, r.output
    project_dir = tmp_path / "bcc-e2e"
    monkeypatch.chdir(project_dir)

    r = runner.invoke(map_group, ["--entity", "gene", "--relation", "gene_in_disease"])
    assert r.exit_code == 0, r.output
    project_yaml = yaml.safe_load((project_dir / ".biotope" / "project.yaml").read_text())
    assert project_yaml["required_entities"] == ["gene"]
    assert project_yaml["required_relations"] == ["gene_in_disease"]


def test_describe_command_is_gone() -> None:
    """`biotope describe` should no longer exist."""
    from biotope.cli import cli

    runner = CliRunner()
    r = runner.invoke(cli, ["describe", "--help"])
    assert r.exit_code != 0
