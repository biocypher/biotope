"""High-level Croissant→KG operations.

Pure functions shared between the test suite and the biotope CLI verbs
(``biotope map``, ``propose-alignment``, ``discover``, ``build``). They return
JSON-serialisable dicts so the CLI can echo their output verbatim and tests
can assert against structure.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from biotope.croissant.acquisition import infer_datasets_location
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
    dataset = load_from_url(path_str) if path_str.startswith(("http://", "https://")) else load_from_path(path_str)
    mapping = unresolved_scaffold(
        path_str,
        required_entities=required_entities or [],
        required_relations=required_relations or [],
    )
    datasets_location = infer_datasets_location(croissant_path)
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


_ID_LIKE_RE = re.compile(r"(^id$|_id$|_curie$|^curie$)", re.IGNORECASE)


def _id_like_fields(field_names: set[str], id_selectors: dict[str, Any]) -> set[str]:
    """Field names that look like identifiers, or are wired into ``ids:``."""
    return {f for f in field_names if _ID_LIKE_RE.search(f) or f in id_selectors}


def _score_join_field(field: str, id_like: set[str]) -> tuple[int, str]:
    """Rank candidates: id-like fields first, then alphabetical for stability."""
    return (0 if field in id_like else 1, field)


def propose_alignment(
    mapping_paths: list[str | Path],
    *,
    write_to: str | Path | None = None,
) -> dict[str, Any]:
    """Propose an ``alignment.yaml`` by spotting overlap in entity property names.

    Operates over semantic entity keys (the mapping key, which is also the
    generated ``input_label``).

    Heuristic, not authoritative: pairs across different ``schema_term``s are
    only proposed when the shared field is id-like (named ``id``/``*_id``/
    ``*_curie`` or referenced from ``ids:``), since incidental shared fields
    (e.g. ``species: human``) are a weak signal for "same node type". Every
    proposal carries a ``confidence``/``reason`` so a human reviews before
    ``build`` — this function never writes anything but the proposal itself.
    """
    mappings = [(Path(p).stem.replace(".mapping", ""), load_mapping(p)) for p in mapping_paths]

    equivalences: list[Equivalence] = []
    reason = "need >=2 mappings to propose cross-mapping equivalences" if len(mappings) < 2 else None

    for i, (stem_a, mapping_a) in enumerate(mappings):
        for stem_b, mapping_b in mappings[i + 1 :]:
            for ent_key_a, entity_a in mapping_a.entities.items():
                for ent_key_b, entity_b in mapping_b.entities.items():
                    shared = set(entity_a.properties).intersection(entity_b.properties)
                    if not shared:
                        continue
                    id_like = _id_like_fields(shared, mapping_a.ids) | _id_like_fields(shared, mapping_b.ids)
                    different_type = (
                        entity_a.schema_term is not None
                        and entity_b.schema_term is not None
                        and entity_a.schema_term != entity_b.schema_term
                    )
                    if different_type and not id_like:
                        # Different declared types sharing only incidental
                        # fields (e.g. `species`) — too weak to propose.
                        continue
                    join_field = min(shared, key=lambda f: _score_join_field(f, id_like))
                    is_id_like = join_field in id_like
                    confidence = 0.9 if is_id_like and not different_type else 0.6 if is_id_like else 0.3
                    reason_text = (
                        f"shared id-like field `{join_field}`"
                        if is_id_like
                        else f"shared field `{join_field}` (not id-like; review before building)"
                    )
                    equivalences.append(
                        Equivalence(
                            a=Reference(mapping=stem_a, node_type=ent_key_a),
                            b=Reference(mapping=stem_b, node_type=ent_key_b),
                            kind=EquivalenceKind.SAME_NODE,
                            join_on=JoinKeys(a=join_field, b=join_field),
                            confidence=confidence,
                            reason=reason_text,
                        ),
                    )

    alignment = Alignment(mappings=[str(p) for p in mapping_paths], equivalences=equivalences)
    payload = alignment.model_dump(by_alias=True, exclude_defaults=False, mode="json")
    yaml_text = yaml.safe_dump(payload, sort_keys=False)
    if write_to is not None:
        Path(write_to).write_text(yaml_text)
    result = {"alignment": payload, "yaml": yaml_text, "wrote": str(write_to) if write_to else None}
    if reason is not None:
        result["reason"] = reason
    return result


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
