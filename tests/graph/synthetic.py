"""Synthetic Biotope projects and Croissant manifests, built in code for the source inventory tests."""

import importlib
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import ModuleType

from click.testing import CliRunner, Result

from biotope.cli import cli
from biotope.graph.check import check_pipeline, check_workspace
from biotope.graph.inventory import generate_source_packages, plan_sources
from biotope.graph.reports import CheckFailed
from biotope.graph.workspace import select_workspace


CONTEXT = {"cr": "http://mlcommons.org/croissant/", "sc": "https://schema.org/"}


def file_object(identity, content, *, name=None, fmt="text/csv", sha="0" * 64, contained=None):
    item = {"@id": identity, "@type": "cr:FileObject", "contentUrl": content, "encodingFormat": fmt, "sha256": sha}
    if name is not None:
        item["name"] = name
    if contained is not None:
        item["containedIn"] = {"@id": contained}
    return item


def pdf(identity, content):
    return file_object(identity, content, name=Path(content).name, fmt="application/pdf")


def record_set(identity, *columns, file="data", data_type="sc:Text"):
    return {
        "@id": identity,
        "@type": "cr:RecordSet",
        "field": [
            {
                "@id": f"{identity}/{column}",
                "name": column,
                "dataType": data_type,
                "source": {"fileObject": {"@id": file}, "extract": {"column": column}},
            }
            for column in columns
        ],
    }


class Project:
    """A Biotope project with a scaffolded graph workspace and managed manifests."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (root / ".biotope/datasets").mkdir(parents=True)
        created = CliRunner().invoke(cli, ["graph", "scaffold", "--graph", str(self.graph)])
        assert created.exit_code == 0, created.output
        pipeline = self.graph / "pipelines/build_graph.py"
        pipeline.write_text(
            pipeline.read_text().replace('name="",', 'name="lifecycle",').replace('scope="",', 'scope="synthetic",')
        )

    @property
    def graph(self) -> Path:
        return self.root / "graph"

    @property
    def sources(self) -> Path:
        return self.graph / "sources"

    @property
    def store(self) -> set[str]:
        directory = self.root / ".biotope/contracts"
        return {path.name for path in directory.iterdir()} if directory.is_dir() else set()

    def manifest(self, name, record_sets=(), distribution=(), context=None) -> Path:
        path = self.root / ".biotope/datasets" / f"{name}.jsonld"
        data = {
            "@context": CONTEXT if context is None else context,
            "name": name,
            "distribution": list(distribution),
            "recordSet": list(record_sets),
        }
        path.write_text(json.dumps(data, indent=2))
        return path

    def study(self, *record_sets, files=()) -> Path:
        return self.manifest("study", record_sets, [file_object("data", "d"), *files])

    def implemented_study(self, *record_sets, files=()) -> Path:
        manifest = self.study(*record_sets, files=files)
        plan = self.generate(manifest)
        self.mark_implemented(*(f"study/{status.package}" for status in plan.statuses))
        return manifest

    def edit(self, path: Path, change) -> None:
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data, indent=2))

    def generate(self, manifest: Path, package=None):
        return generate_source_packages(manifest, self.sources, package)

    def mark_implemented(self, *packages: str) -> None:
        for package in packages:
            loader = self.sources / package / "loader.py"
            loader.write_text(loader.read_text().split("\n", 1)[1])

    def acknowledge_drift(self, manifest: Path) -> None:
        for status in plan_sources(manifest, self.sources).statuses:
            if status.state == "drift":
                schema = status.path / "schema.py"
                schema.write_text(schema.read_text().replace(status.acknowledged, status.revision))

    def author_inventory(self) -> None:
        inventory = self.sources / "inventory.py"
        inventory.write_text("# authored\n" + inventory.read_text())

    def exclude(self, reasons: dict[str, str]) -> None:
        selection = self.sources / "__init__.py"
        text = selection.read_text()
        start = text.index("EXCLUDED_SOURCES: dict[str, str] = ")
        end = text.index("\n", start)
        selection.write_text(text[:start] + f"EXCLUDED_SOURCES: dict[str, str] = {reasons!r}" + text[end:])

    def report(self, **pipeline_changes) -> dict:
        """Check the workspace, with Pipeline fields replaced by values or by functions of the pipeline."""
        with select_workspace(self.graph) as workspace:
            try:
                if not pipeline_changes:
                    return check_workspace(workspace, static=False)
                pipeline = workspace.pipeline()
                changes = {
                    key: value(pipeline) if callable(value) else value for key, value in pipeline_changes.items()
                }
                return check_pipeline(replace(pipeline, **changes), workspace=workspace, static=False)
            except CheckFailed as exc:
                return exc.report

    def findings(self, **pipeline_changes) -> list[dict]:
        return self.report(**pipeline_changes)["findings"]

    def codes(self, severity=None, **pipeline_changes) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for finding in self.findings(**pipeline_changes):
            if severity is None or finding["severity"] == severity:
                found.setdefault(finding["code"], []).append(finding["subject"])
        return found

    def messages(self, code: str) -> list[str]:
        return [finding["message"] for finding in self.findings() if finding["code"] == code]

    @contextmanager
    def imported(self, module: str) -> Iterator[ModuleType]:
        sys.path.insert(0, str(self.root))
        try:
            yield importlib.import_module(module)
        finally:
            sys.path.remove(str(self.root))
            for name in [name for name in sys.modules if name == "graph" or name.startswith("graph.")]:
                del sys.modules[name]

    def run(self, *args: str) -> Result:
        previous = Path.cwd()
        os.chdir(self.root)
        try:
            return CliRunner().invoke(cli, list(args))
        finally:
            os.chdir(previous)

    def snapshot(self) -> dict[Path, bytes]:
        return {path: path.read_bytes() for path in self.sources.rglob("*") if path.is_file()}


def states(plan) -> dict[str, str]:
    return {status.package: status.state for status in plan.statuses}
