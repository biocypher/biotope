"""Resolve conventional graph registrations inside one selected workspace."""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from collections import Counter
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import cast

from biotope.extraction import Extraction
from biotope.graph.contracts import Pipeline
from biotope.graph.reports import Finding
from biotope.graph.revisions import project_root
from biotope.graph.survey import Survey, inventory_findings, survey_sources
from biotope.graph.topology import Topology


class WorkspaceLoadFailed(ValueError):
    """The pipeline cannot be imported; ``findings`` still holds everything static discovery found."""

    def __init__(self, message: str, findings: tuple[Finding, ...]) -> None:
        super().__init__(message)
        self.findings = findings


@dataclass(frozen=True)
class Workspace:
    root: Path
    package: str

    @cached_property
    def surveys(self) -> tuple[Survey, ...]:
        sources = self.root / "sources"
        return (survey_sources(sources, project_root(self.root)),) if sources.is_dir() else ()

    def pipeline(self) -> Pipeline:
        """Import the pipeline, after static discovery, so that its findings survive an import failure."""
        surveys = self.surveys
        try:
            value = getattr(importlib.import_module(f"{self.package}.pipelines.build_graph"), "PIPELINE")
            if not isinstance(value, Pipeline):
                raise ValueError("pipelines/build_graph.py must declare PIPELINE as a biotope.graph.Pipeline")
        except Exception as exc:
            findings = (
                *inventory_findings(surveys, None),
                Finding("workspace.load", "error", str(self.root), str(exc)),
            )
            raise WorkspaceLoadFailed(str(exc), findings) from exc
        return value

    def extractions(self) -> tuple[Extraction, ...]:
        if not (self.root / "extraction" / "__init__.py").is_file():
            return ()
        value: object = getattr(importlib.import_module(f"{self.package}.extraction"), "EXTRACTIONS", None)
        listed = cast(tuple[object, ...], value) if isinstance(value, tuple) else None
        if listed is None or not all(isinstance(item, Extraction) for item in listed):
            raise ValueError(
                "extraction/__init__.py must declare EXTRACTIONS as a tuple of biotope.extraction.Extraction"
            )
        extractions = cast(tuple[Extraction, ...], listed)
        twice = sorted(name for name, count in Counter(item.name for item in extractions).items() if count > 1)
        if twice:
            raise ValueError(f"extraction/__init__.py lists the extraction {', '.join(twice)} more than once")
        return extractions

    def topology(self) -> Topology:
        value = getattr(importlib.import_module(f"{self.package}.topology"), "TOPOLOGY")
        if not isinstance(value, Topology):
            raise ValueError("topology/__init__.py must declare TOPOLOGY as a biotope.graph.Topology")
        return value


@contextmanager
def select_workspace(root: Path) -> Generator[Workspace, None, None]:
    """Anchor relative inputs to the workspace parent and isolate its imports."""
    root = root.resolve()
    if not (root / "__init__.py").is_file():
        raise ValueError(f"No graph workspace at {root}; run biotope graph scaffold or select --graph <folder>")
    package = root.name if root.name.isidentifier() and root.name != "biotope" else "_biotope_workspace"
    previous = {k: v for k, v in sys.modules.items() if k == package or k.startswith(package + ".")}
    for key in previous:
        del sys.modules[key]
    old_path, old_cwd = sys.path[:], Path.cwd()
    try:
        os.chdir(root.parent)
        sys.path.insert(0, str(root.parent))
        spec = importlib.util.spec_from_file_location(
            package, root / "__init__.py", submodule_search_locations=[str(root)]
        )
        if spec is None or spec.loader is None:
            raise ValueError(f"Cannot import graph workspace {root}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[package] = module
        spec.loader.exec_module(module)
        yield Workspace(root, package)
    finally:
        os.chdir(old_cwd)
        sys.path[:] = old_path
        for key in list(sys.modules):
            if key == package or key.startswith(package + "."):
                del sys.modules[key]
        sys.modules.update(previous)
