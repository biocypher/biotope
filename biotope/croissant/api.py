"""High-level Croissant→KG operations.

Pure functions shared between the test suite and the biotope CLI verbs
(``biotope map``). They return
JSON-serialisable dicts so the CLI can echo their output verbatim and tests
can assert against structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from biotope.croissant.mapping.defaults import intent_comment, unresolved_scaffold
from biotope.croissant.mapping.render import (
    build_inspector_appendix,
    render_mapping_with_appendix,
)
from biotope.croissant.spec import load_from_path, load_from_url


def _load_problem(problem_yaml: str | Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(problem_yaml).read_text())
    if not isinstance(data, dict):
        msg = f"problem.yaml must be a mapping, got {type(data).__name__}"
        raise TypeError(msg)
    return data


def propose_decomposition(problem_yaml: str | Path) -> dict[str, Any]:
    """Parse a ``project.yaml`` / ``problem.yaml`` into a decomposition skeleton."""
    problem = _load_problem(problem_yaml)
    return {
        "purpose": problem.get("purpose", problem.get("problem", "")),
        "required_entities": list(problem.get("required_entities", [])),
        "required_relations": list(problem.get("required_relations", [])),
        "notes": problem.get("notes", ""),
    }


def scaffold_mapping(
    croissant_path: str | Path,
    *,
    required_entities: list[str] | None = None,
    required_relations: list[str] | None = None,
    purpose: str | None = None,
    write_to: str | Path | None = None,
) -> dict[str, Any]:
    """Generate an unresolved semantic mapping scaffold for a Croissant file.

    The scaffold is heuristic-free: slot keys are normalised from the supplied
    ``required_entities`` / ``required_relations`` lists, all selectors and
    record_set choices are left unresolved, and the inspector output is
    appended as a YAML comment block.
    """
    path_str = str(croissant_path)
    dataset = load_from_url(path_str) if path_str.startswith(("http://", "https://")) else load_from_path(path_str)
    mapping = unresolved_scaffold(
        path_str,
        required_entities=required_entities or [],
        required_relations=required_relations or [],
    )
    appendix = build_inspector_appendix(
        dataset,
    )
    comment = intent_comment(
        required_entities=required_entities or [],
        required_relations=required_relations or [],
        purpose=purpose,
    )
    scaffold = render_mapping_with_appendix(
        mapping,
        appendix=appendix,
        intent_comment=comment,
    )
    if write_to is not None:
        Path(write_to).write_text(scaffold)
    # "unresolved" here means "slots that still need binding" — including
    # empty stubs the scaffold just laid down. ``Mapping.unresolved_slots``
    # excludes empty stubs (they're inactive, not broken), so for the
    # scaffold's user-facing TODO we compute the full not-resolved list.
    todo = [f"entities.{name}" for name, entity in mapping.entities.items() if not entity.is_resolved()] + [
        f"relations.{name}" for name, relation in mapping.relations.items() if not relation.is_resolved()
    ]
    return {
        "yaml": scaffold,
        "wrote": str(write_to) if write_to else None,
        "unresolved": todo,
    }


# Backwards-compatible alias (the deprecated `propose-mapping` CLI forwards here).
def propose_mapping(
    croissant_path: str | Path,
    *,
    write_to: str | Path | None = None,
    required_entities: list[str] | None = None,
    required_relations: list[str] | None = None,
    purpose: str | None = None,
) -> dict[str, Any]:
    """Deprecated: identical to :func:`scaffold_mapping`."""
    return scaffold_mapping(
        croissant_path,
        write_to=write_to,
        required_entities=required_entities,
        required_relations=required_relations,
        purpose=purpose,
    )


def materialize(
    project_dir: str | Path,
    mapping_paths: list[str | Path],
    alignment_path: str | Path | None = None,
    *,
    required_entities: list[str] | None = None,
    required_relations: list[str] | None = None,
    target: str = "csv",
) -> dict[str, Any]:
    """Write a runnable BioCypher project to ``project_dir``.

    Pass ``required_entities`` / ``required_relations`` (typically from
    ``project.yaml``) to enable the project-wide coverage check: every
    declared slot must be resolved in at least one mapping.

    ``target`` (``"csv"`` or ``"neo4j"``) sets the ``dbms:`` written into a
    freshly-created ``biocypher_config.yaml``; ignored if that file already
    exists (biotope never overwrites a user-authored config).
    """
    from biotope.croissant.scaffold.materialize import materialize_project

    return materialize_project(
        project_dir=Path(project_dir),
        mapping_paths=[Path(p) for p in mapping_paths],
        alignment_path=Path(alignment_path) if alignment_path is not None else None,
        required_entities=required_entities,
        required_relations=required_relations,
        target=target,
    )
