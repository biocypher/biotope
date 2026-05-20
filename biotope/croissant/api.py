"""High-level Croissant→KG operations.

Pure functions shared between the test suite and the biotope CLI verbs
(``biotope map``, ``propose-alignment``, ``discover``, ``build``). They return
JSON-serialisable dicts so the CLI can echo their output verbatim and tests
can assert against structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from biotope.croissant.alignment.model import (
    Alignment,
    Equivalence,
    EquivalenceKind,
    JoinKeys,
    Reference,
)
from biotope.croissant.mapping.defaults import intent_comment, unresolved_scaffold
from biotope.croissant.mapping.loader import load_mapping
from biotope.croissant.mapping.render import (
    build_inspector_appendix,
    render_mapping_with_appendix,
)
from biotope.croissant.registry.client import LocalRegistryClient, RegistryClient
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


def discover_sources(
    decomposition: dict[str, Any],
    registry_paths: list[str | Path] | None = None,
    local_baker_dir: str | Path | None = None,
    http_registry_url: str | None = None,
) -> dict[str, Any]:
    """Rank candidate Croissant files and registered adapters for a decomposition."""
    required = set(decomposition.get("required_entities", []))
    clients: list[RegistryClient] = []
    for p in registry_paths or []:
        clients.append(LocalRegistryClient(p))
    if http_registry_url is not None:
        from biotope.croissant.registry.client import HttpRegistryClient

        clients.append(HttpRegistryClient(http_registry_url))

    adapter_matches: list[dict[str, Any]] = []
    for client in clients:
        for meta in client.list_adapters():
            overlap = required.intersection(meta.produced_entities)
            if not overlap:
                continue
            adapter_matches.append(
                {
                    "identifier": meta.identifier,
                    "name": meta.name,
                    "code_repository": meta.code_repository,
                    "croissant_file": meta.croissant_file,
                    "matched_entities": sorted(overlap),
                    "score": len(overlap),
                },
            )
    adapter_matches.sort(key=lambda m: m["score"], reverse=True)

    croissant_files: list[dict[str, Any]] = []
    if local_baker_dir is not None:
        for path in sorted(Path(local_baker_dir).glob("**/*.jsonld")):
            croissant_files.append({"path": str(path), "source": "local_baker"})
        for path in sorted(Path(local_baker_dir).glob("**/*.croissant.json")):
            croissant_files.append({"path": str(path), "source": "local_baker"})

    return {
        "adapter_matches": adapter_matches,
        "croissant_files": croissant_files,
        "required_entities": sorted(required),
    }


def scaffold_mapping(
    croissant_path: str | Path,
    *,
    required_entities: list[str] | None = None,
    required_relations: list[str] | None = None,
    purpose: str | None = None,
    write_to: str | Path | None = None,
    preview_rows: int = 3,
) -> dict[str, Any]:
    """Generate an unresolved semantic mapping scaffold for a Croissant file.

    The scaffold is heuristic-free: slot keys are normalised from the supplied
    ``required_entities`` / ``required_relations`` lists, all selectors and
    record_set choices are left unresolved, and the inspector output is
    appended as a YAML comment block.
    """
    path_str = str(croissant_path)
    dataset = (
        load_from_url(path_str)
        if path_str.startswith(("http://", "https://"))
        else load_from_path(path_str)
    )
    mapping = unresolved_scaffold(
        path_str,
        required_entities=required_entities or [],
        required_relations=required_relations or [],
    )
    datasets_location = _infer_datasets_location(croissant_path)
    appendix = build_inspector_appendix(
        dataset,
        datasets_location=datasets_location,
        preview_rows=preview_rows,
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
    return {
        "yaml": scaffold,
        "wrote": str(write_to) if write_to else None,
        "unresolved": mapping.unresolved_slots(),
    }


# Backwards-compatible alias (the deprecated `propose-mapping` CLI forwards here).
def propose_mapping(
    croissant_path: str | Path,
    *,
    write_to: str | Path | None = None,
    preview_rows: int = 3,
    required_entities: list[str] | None = None,
    required_relations: list[str] | None = None,
    purpose: str | None = None,
) -> dict[str, Any]:
    """Deprecated: identical to :func:`scaffold_mapping`."""
    return scaffold_mapping(
        croissant_path,
        write_to=write_to,
        preview_rows=preview_rows,
        required_entities=required_entities,
        required_relations=required_relations,
        purpose=purpose,
    )


def _infer_datasets_location(croissant_path: str | Path) -> Path | None:
    """Best-effort on-disk data root for preview sampling.

    For Croissants under ``.biotope/datasets/<rel>.jsonld`` returns the matching
    ``<project>/<rel>/`` data directory; ``includes`` paths in baker-generated
    Croissants are relative to that directory, not to the project root.
    """
    path_str = str(croissant_path)
    if path_str.startswith(("http://", "https://")):
        return None

    path = Path(path_str).resolve()
    for parent in path.parents:
        if parent.name == "datasets" and parent.parent.name == ".biotope":
            biotope_root = parent.parent.parent
            try:
                rel = path.relative_to(parent).with_suffix("")
            except ValueError:
                return biotope_root
            data_dir = biotope_root / rel
            if data_dir.exists():
                return data_dir if data_dir.is_dir() else data_dir.parent
            return biotope_root
    return path.parent


def propose_alignment(
    mapping_paths: list[str | Path],
    *,
    write_to: str | Path | None = None,
) -> dict[str, Any]:
    """Propose an ``alignment.yaml`` by spotting overlap in entity property names.

    Operates over semantic entity keys (the mapping key, which is also the
    generated ``input_label``).
    """
    mappings = [(Path(p).stem.replace(".mapping", ""), load_mapping(p)) for p in mapping_paths]
    equivalences: list[Equivalence] = []

    for i, (stem_a, mapping_a) in enumerate(mappings):
        for stem_b, mapping_b in mappings[i + 1 :]:
            for ent_key_a, entity_a in mapping_a.entities.items():
                for ent_key_b, entity_b in mapping_b.entities.items():
                    shared = set(entity_a.properties).intersection(entity_b.properties)
                    if not shared:
                        continue
                    join_field = sorted(shared)[0]
                    equivalences.append(
                        Equivalence(
                            a=Reference(mapping=stem_a, node_type=ent_key_a),
                            b=Reference(mapping=stem_b, node_type=ent_key_b),
                            kind=EquivalenceKind.SAME_NODE,
                            join_on=JoinKeys(a=join_field, b=join_field),
                        ),
                    )

    alignment = Alignment(
        mappings=[str(p) for p in mapping_paths],
        equivalences=equivalences,
    )
    payload = alignment.model_dump(by_alias=True, exclude_defaults=False, mode="json")
    yaml_text = yaml.safe_dump(payload, sort_keys=False)
    if write_to is not None:
        Path(write_to).write_text(yaml_text)
    return {"alignment": payload, "yaml": yaml_text, "wrote": str(write_to) if write_to else None}


def materialize(
    project_dir: str | Path,
    mapping_paths: list[str | Path],
    alignment_path: str | Path | None = None,
) -> dict[str, Any]:
    """Write a runnable BioCypher project to ``project_dir``."""
    from biotope.croissant.scaffold.materialize import materialize_project

    return materialize_project(
        project_dir=Path(project_dir),
        mapping_paths=[Path(p) for p in mapping_paths],
        alignment_path=Path(alignment_path) if alignment_path is not None else None,
    )
