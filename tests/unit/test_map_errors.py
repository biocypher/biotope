"""Friendly-error tests for `biotope map` when the wrong file type is passed."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from biotope.commands.init import init
from biotope.commands.map import map_group


@pytest.fixture
def minimal_croissant_jsonld() -> Path:
    return Path(__file__).parent.parent / "fixtures" / "croissant" / "minimal.croissant.json"


def _init_project(tmp_path: Path) -> Path:
    runner = CliRunner()
    r = runner.invoke(init, ["proj", "--dir", str(tmp_path), "--no-git", "--no-prompt"])
    assert r.exit_code == 0, r.output
    return tmp_path / "proj"


def test_map_rejects_biotope_yaml_scaffold(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    data_dir = project_dir / "data" / "inputs" / "ot"
    data_dir.mkdir(parents=True)
    (data_dir / ".biotope.yaml").write_text("# annotation scaffold\nfoo: bar\n")

    r = runner.invoke(map_group, ["-c", str(data_dir / ".biotope.yaml")])
    assert r.exit_code != 0
    assert "annotate scaffold" in r.output
    assert ".biotope/datasets" in r.output


def test_map_suggests_canonical_croissant_jsonld(tmp_path: Path, monkeypatch) -> None:
    """When the per-directory Croissant exists at the canonical path, suggest it."""
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    data_dir = project_dir / "data" / "inputs" / "ot"
    data_dir.mkdir(parents=True)
    (data_dir / ".biotope.yaml").write_text("dataset: {}\n")

    # Simulate the canonical layout: .biotope/datasets/<rel>.jsonld (file, not dir).
    canonical = project_dir / ".biotope" / "datasets" / "data" / "inputs" / "ot.jsonld"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("{}\n")

    r = runner.invoke(map_group, ["-c", str(data_dir / ".biotope.yaml")])
    assert r.exit_code != 0
    assert ".biotope/datasets/data/inputs/ot.jsonld" in r.output


def test_map_inspect_rejects_yaml(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    yaml_file = project_dir / "data" / "some.yaml"
    yaml_file.parent.mkdir(parents=True, exist_ok=True)
    yaml_file.write_text("not: json-ld\n")

    r = runner.invoke(map_group, ["inspect", str(yaml_file)])
    assert r.exit_code != 0
    assert "JSON-LD" in r.output


def test_map_inspect_rejects_missing_file(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    r = runner.invoke(map_group, ["inspect", str(project_dir / "nope.jsonld")])
    assert r.exit_code != 0
    assert "not found" in r.output


def test_map_accepts_data_dir_and_resolves_canonical_croissant(
    tmp_path: Path, monkeypatch, minimal_croissant_jsonld: Path
) -> None:
    """`biotope map -c <data_dir>` should resolve to .biotope/datasets/<rel>.jsonld."""
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    data_dir = project_dir / "data" / "inputs" / "ot"
    data_dir.mkdir(parents=True)
    (data_dir / "dummy.txt").write_text("placeholder")

    canonical = project_dir / ".biotope" / "datasets" / "data" / "inputs" / "ot.jsonld"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text(minimal_croissant_jsonld.read_text())

    # Passing the data directory should resolve to the canonical jsonld and proceed
    # far enough to invoke the wizard's CLI prompt loop (we kill it with EOF).
    r = runner.invoke(map_group, ["-c", str(data_dir)], input="\n\n\n\n")
    # Wizard will eventually fail on EOF; we just need to confirm it got past
    # the Croissant-resolution step (no "No Croissant for this directory" panel).
    assert "No Croissant for this directory" not in r.output


def test_map_empty_state_recommends_add_first(tmp_path: Path, monkeypatch) -> None:
    """Bare `biotope map` in a fresh project recommends `biotope add` first;
    intent-first remains a secondary path."""
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    r = runner.invoke(map_group, [])
    assert r.exit_code != 0
    assert "biotope add" in r.output
    assert "Add data first" in r.output
    # Intent-first path is still mentioned (secondary).
    assert "--entity" in r.output


def test_map_data_dir_without_add_suggests_add(tmp_path: Path, monkeypatch) -> None:
    """Passing a data directory that hasn't been ingested suggests `biotope add`."""
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    data_dir = project_dir / "data" / "inputs" / "not-yet-added"
    data_dir.mkdir(parents=True)

    r = runner.invoke(map_group, ["-c", str(data_dir)])
    assert r.exit_code != 0
    assert "biotope add" in r.output


def test_map_clear_entities_warns_with_existing_intent(tmp_path: Path, monkeypatch) -> None:
    """`--clear-entities` against a non-empty project must print a destructive
    warning panel listing what would be dropped. The flag still works."""
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    # Seed required_entities.
    seed = runner.invoke(
        map_group,
        ["--entity", "gene", "--entity", "drug_target", "--relation", "drug_targets_gene"],
    )
    assert seed.exit_code == 0, seed.output

    # Clear entities only — relations should not be listed.
    r = runner.invoke(map_group, ["--clear-entities", "--entity", "compound"])
    assert r.exit_code == 0, r.output
    assert "Destructive" in r.output
    assert "required_entities" in r.output
    assert "gene" in r.output
    assert "drug_target" in r.output
    assert "required_relations" not in r.output


def test_map_clear_entities_silent_when_already_empty(tmp_path: Path, monkeypatch) -> None:
    """No warning when there's nothing to drop."""
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    r = runner.invoke(map_group, ["--clear-entities", "--entity", "gene"])
    assert r.exit_code == 0, r.output
    assert "Destructive" not in r.output


def test_map_clear_relations_warns(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    runner.invoke(map_group, ["--relation", "drug_has_mechanism_of_action"])

    r = runner.invoke(map_group, ["--clear-relations"])
    assert r.exit_code == 0, r.output
    assert "Destructive" in r.output
    assert "required_relations" in r.output
    assert "drug_has_mechanism_of_action" in r.output


def test_map_preview_iterates_all_mappings(tmp_path: Path, monkeypatch, minimal_croissant_jsonld: Path) -> None:
    """`biotope map preview` (no args) must preview every mapping in the project,
    not abort on multi-mapping projects. Regression for B6."""
    from biotope.croissant.mapping import Mapping, dump_mapping

    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    croissant = project_dir / "data" / "minimal.croissant.json"
    croissant.parent.mkdir(parents=True, exist_ok=True)
    croissant.write_text(minimal_croissant_jsonld.read_text())

    mappings_dir = project_dir / "mappings"
    mappings_dir.mkdir(exist_ok=True)
    for stem in ("first", "second"):
        mapping = Mapping.model_validate(
            {
                "croissant": str(croissant),
                "entities": {
                    "gene": {"record_set": "genes", "id": "ensembl_id"},
                },
            }
        )
        dump_mapping(mapping, mappings_dir / f"{stem}.mapping.yaml")

    r = runner.invoke(map_group, ["preview"])
    assert r.exit_code == 0, r.output
    assert "first.mapping.yaml" in r.output
    assert "second.mapping.yaml" in r.output


def test_map_inspect_rejects_invalid_json(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_dir = _init_project(tmp_path)
    monkeypatch.chdir(project_dir)

    bad = project_dir / "bad.json"
    bad.write_text("{not json")

    r = runner.invoke(map_group, ["inspect", str(bad)])
    assert r.exit_code != 0
    assert "Invalid Croissant" in r.output
