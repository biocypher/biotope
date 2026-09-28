"""The `biotope source generate` command: what it reports, warns about, stages in Git, and refuses."""

import json
import re
import shutil
import subprocess

import pytest
from synthetic import record_set

from biotope.graph.inventory import plan_sources


def generate(project, manifest, *flags):
    return project.run("source", "generate", str(manifest), "--out", "graph/sources", *flags)


def test_generate_refuses_a_conflict_and_names_what_it_would_have_created(project):
    manifest = project.study(record_set("rows", "x"))
    project.generate(manifest)
    shutil.copytree(project.sources / "study/rows", project.sources / "study/copy")
    project.edit(manifest, lambda data: data["recordSet"].append(record_set("more", "y")))
    files, history = project.snapshot(), set(project.store)
    for flags in ([], ["--check"]):
        result = generate(project, manifest, *flags)
        assert result.exit_code != 0 and "nothing was written" in result.output
        assert "Would create graph/sources/study/more" in result.stdout and "Created" not in result.stdout
        assert project.snapshot() == files and set(project.store) == history


def test_generate_check_only_warns_about_drift_orphans_and_missing_history(project, tmp_path):
    manifest = project.implemented_study(record_set("rows", "x"), record_set("drifting", "y"), record_set("gone", "z"))
    [rows] = [status for status in plan_sources(manifest, project.sources).statuses if status.package == "rows"]
    (project.root / f".biotope/contracts/{rows.revision}.json").unlink()

    def change(data):
        data["recordSet"].pop()
        data["recordSet"][1]["field"][0]["dataType"] = "sc:Integer"

    project.edit(manifest, change)
    files, history = project.snapshot(), set(project.store)
    checked = generate(project, manifest, "--check")
    assert checked.exit_code == 0, checked.output
    assert re.search(r"^Drift +graph/sources/study/drifting$", checked.output, re.MULTILINE)
    assert re.search(r"^Orphaned +graph/sources/study/gone$", checked.output, re.MULTILINE)
    assert "is acknowledged but not recorded" in checked.output
    assert project.snapshot() == files and set(project.store) == history
    loose = tmp_path / "loose.jsonld"
    loose.write_text(json.dumps({"recordSet": [record_set("r", "x")], "distribution": []}))
    unmanaged = project.run("source", "generate", str(loose), "--out", str(tmp_path / "sources"))
    assert unmanaged.exit_code == 0 and "no contract history is kept" in unmanaged.output


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_generate_stages_the_revisions_it_records(project):
    subprocess.run(["git", "init", "-q"], cwd=project.root, check=True)
    result = generate(project, project.study(record_set("rows", "x")))
    assert result.exit_code == 0, result.output
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=project.root, text=True, capture_output=True, check=True
    )
    assert {f".biotope/contracts/{name}" for name in project.store} <= set(staged.stdout.split())


def test_generate_reports_nothing_as_created_when_writing_fails(project, monkeypatch):
    manifest = project.study(record_set("rows", "x"))

    def refuse(plan):
        raise ValueError("the root changed while generating; nothing was written")

    monkeypatch.setattr("biotope.commands.source.apply_plan", refuse)
    result = generate(project, manifest)
    assert result.exit_code != 0 and "nothing was written" in result.output and "Created" not in result.output
