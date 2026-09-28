"""Third-party distributions that graph code imports, and those its workspace declares."""

from __future__ import annotations

import ast
import importlib.metadata
import re
import sys
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path


if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def canonical(name: str) -> str:
    """Normalize a distribution name the way package indexes compare them."""
    return re.sub(r"[-_.]+", "-", name).lower()


@lru_cache(maxsize=1)
def installed_modules() -> Mapping[str, list[str]]:
    """Scan the installed distributions once per process; the scan takes a noticeable fraction of a second."""
    return importlib.metadata.packages_distributions()


def imported_distributions(files: Iterable[Path]) -> dict[str, list[str]]:
    """Map each installed third-party module the files import to the distributions that provide it."""
    providers = installed_modules()
    modules: set[str] = set()
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
            if isinstance(node, ast.Import):
                modules.update(alias.name.partition(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.partition(".")[0])
    return {
        module: sorted({canonical(name) for name in providers[module]})
        for module in sorted(modules - sys.stdlib_module_names)
        if module in providers
    }


def declared_distributions(pyproject: Path) -> set[str]:
    """Read the distribution names that a pyproject.toml lists in [project].dependencies."""
    if not pyproject.is_file():
        return set()
    with pyproject.open("rb") as stream:
        requirements: list[str] = tomllib.load(stream).get("project", {}).get("dependencies", [])
    return {canonical(match.group()) for item in requirements if (match := re.match(r"[A-Za-z0-9][\w.-]*", item))}
