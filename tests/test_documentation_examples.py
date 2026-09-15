"""Behavior checks for the public configuration inventory example."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


CHECKER = Path(__file__).resolve().parents[1] / "docs/examples/cluster-compliance-checker.py"
REQUIREMENTS = {
    "required_pattern": "cluster-strict",
    "required_fields": ["project_id"],
    "require_remote_validation": True,
}


def run_checker(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    requirements = tmp_path / "requirements.json"
    requirements.write_text(json.dumps(REQUIREMENTS))
    return subprocess.run(
        [sys.executable, str(CHECKER), "--requirements", str(requirements), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def write_project(tmp_path: Path, name: str, **overrides: object) -> Path:
    project = tmp_path / name
    (project / ".biotope").mkdir(parents=True)
    validation = {
        "enabled": True,
        "validation_pattern": "cluster-strict",
        "minimum_required_fields": ["project_id"],
        "remote_config": {"url": "https://cluster.example.org/validation.yaml"},
        **overrides,
    }
    (project / ".biotope/config.yaml").write_text(yaml.safe_dump({"annotation_validation": validation}))
    return project


def test_json_scan_uses_actual_requirement_results(tmp_path: Path) -> None:
    write_project(tmp_path, "matching")
    write_project(tmp_path, "disabled", enabled=False)
    write_project(tmp_path, "missing-field", minimum_required_fields=[])
    result = run_checker(tmp_path, "--scan-dir", str(tmp_path), "--json")
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["scope"] == "local_configuration"
    assert report["summary"] == {"projects": 3, "matching": 1, "not_matching": 2}
    assert sum(project["matches_requirements"] for project in report["projects"]) == 1


def test_literal_label_matches_even_with_cluster_in_url(tmp_path: Path) -> None:
    project = write_project(tmp_path, "matching")
    result = run_checker(tmp_path, "--project", str(project), "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout)["projects"][0]["validation_pattern"] == "cluster-strict"


def test_empty_scan_reports_no_projects_without_dividing_by_zero(tmp_path: Path) -> None:
    result = run_checker(tmp_path, "--scan-dir", str(tmp_path))
    assert result.returncode == 1
    assert "No Biotope projects found" in result.stdout
    assert not result.stderr


@pytest.mark.parametrize("content", ["invalid: [yaml", "- not a mapping", "annotation_validation: null"])
def test_unreadable_configuration_is_a_reported_mismatch(tmp_path: Path, content: str) -> None:
    project = write_project(tmp_path, "invalid")
    (project / ".biotope/config.yaml").write_text(content)
    result = run_checker(tmp_path, "--project", str(project), "--json")
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["summary"]["not_matching"] == 1
    assert "Cannot read configuration" in report["projects"][0]["issues"][0]


def test_json_report_file_contains_the_same_summary(tmp_path: Path) -> None:
    project = write_project(tmp_path, "matching")
    output = tmp_path / "report.json"
    result = run_checker(tmp_path, "--project", str(project), "--json", "--report", str(output))
    assert result.returncode == 0
    assert result.stdout == ""
    assert json.loads(output.read_text())["summary"]["matching"] == 1
