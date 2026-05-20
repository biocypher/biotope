"""Schema for ``.biotope/project.yaml`` — the competence-questions document.

This document captures what the user wants the knowledge graph to answer,
*not* technical configuration. It is the canonical agent surface: an agent
populates it via ``biotope describe`` flags, and downstream commands
(``propose-mapping``, ``discover``, ``build``) consult it.

Hierarchical config precedence (lower wins, higher overrides):

1. ``~/.config/biotope/config.yaml`` — user-level defaults
2. ``.biotope/config.yaml`` — project technical config (biotope-managed)
3. ``.biotope/project.yaml`` — project content intent (this document)
4. CLI flags — final say
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Project(BaseModel):
    """Competence-questions document for a biotope project."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str
    purpose: str = ""
    """Free-text competence question(s). The single most important field."""

    required_entities: list[str] = Field(default_factory=list)
    """Entity types the graph must contain to answer ``purpose``.

    Free text. Typically nouns (``drug``, ``gene``, ``customer``). No
    snake_case enforcement; downstream commands treat these as natural-
    language hints when matching against schemas and registries.
    """

    required_relations: list[str] = Field(default_factory=list)
    """Relations between entities.

    Free text. Either short labels (``drug_targets_gene``) or natural-
    language statements (``which drugs target which proteins``) are accepted;
    downstream matching is intentionally fuzzy.
    """

    data_sources: list[str] = Field(default_factory=list)
    """Croissant files, registry IDs, or URLs the user has on hand."""

    notes: str = ""

    @classmethod
    def load(cls, path: str | Path) -> Project:
        """Load and validate a project YAML."""
        data = yaml.safe_load(Path(path).read_text()) or {}
        return cls.model_validate(data)

    def dump(self, path: str | Path) -> None:
        """Serialise to YAML at ``path``."""
        payload = self.model_dump(exclude_defaults=False)
        Path(path).write_text(yaml.safe_dump(payload, sort_keys=False))


def resolve_project_path(start: Path | None = None, *, visible: bool = False) -> Path:
    """Return the path where ``project.yaml`` lives for the project at ``start``.

    If ``visible``, the file lives at the project root (``project.yaml``);
    otherwise under ``.biotope/project.yaml``.
    """
    base = start if start is not None else Path.cwd()
    return (base / "project.yaml") if visible else (base / ".biotope" / "project.yaml")


def find_project(start: Path | None = None) -> Path | None:
    """Walk upward from ``start`` to find the nearest ``project.yaml``.

    Checks both the visible (``project.yaml``) and hidden
    (``.biotope/project.yaml``) locations.
    """
    cur = (start if start is not None else Path.cwd()).resolve()
    for parent in [cur, *cur.parents]:
        for candidate in (parent / ".biotope" / "project.yaml", parent / "project.yaml"):
            if candidate.is_file():
                return candidate
    return None


def merge_overrides(project: Project, **overrides: Any) -> Project:
    """Return a new Project with non-``None`` overrides merged in."""
    data = project.model_dump()
    for key, value in overrides.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)) and not value:
            continue
        data[key] = value
    return Project.model_validate(data)
