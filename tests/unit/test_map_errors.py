from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from biotope.commands.init import init
from biotope.commands.map import map_group


MINIMAL_CROISSANT = Path(__file__).parent.parent / "fixtures" / "croissant" / "minimal.croissant.json"


def test_map_inspect_resolves_a_data_folder_and_refuses_a_missing_yaml_or_invalid_file(
    tmp_path: Path, monkeypatch
) -> None:
    runner = CliRunner(mix_stderr=False)
    created = runner.invoke(init, ["proj", "--dir", str(tmp_path), "--no-prompt"])
    assert created.exit_code == 0, created.output
    project_dir = tmp_path / "proj"
    monkeypatch.chdir(project_dir)
    (project_dir / "data" / "inputs" / "ot").mkdir(parents=True)
    canonical = project_dir / ".biotope" / "datasets" / "data" / "inputs" / "ot.jsonld"
    canonical.parent.mkdir(parents=True)
    canonical.write_text(MINIMAL_CROISSANT.read_text())

    resolved = runner.invoke(map_group, ["inspect", "data/inputs/ot", "--json"])
    assert resolved.exit_code == 0, resolved.output
    [genes] = json.loads(resolved.stdout)["record_sets"]
    assert genes["name"] == "genes"
    assert genes["fields"][0]["name"] == "ensembl_id"

    (project_dir / "some.yaml").write_text("not: json-ld\n")
    (project_dir / "bad.json").write_text("{not json")
    for path, message in (("some.yaml", "JSON-LD"), ("nope.jsonld", "not found"), ("bad.json", "Invalid Croissant")):
        refused = runner.invoke(map_group, ["inspect", path, "--json"])
        assert refused.exit_code != 0
        assert refused.stdout == ""
        assert message in refused.stderr
