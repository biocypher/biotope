"""Resolve conventional graph registrations inside one selected workspace."""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from biotope.graph.contracts import Pipeline
from biotope.graph.topology import Topology


@dataclass(frozen=True)
class Workspace:
    root: Path
    package: str

    def pipeline(self) -> Pipeline:
        value = getattr(importlib.import_module(f"{self.package}.pipelines.build_graph"), "PIPELINE")
        if not isinstance(value, Pipeline):
            raise ValueError("pipelines/build_graph.py must declare PIPELINE as a biotope.graph.Pipeline")
        return value

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
