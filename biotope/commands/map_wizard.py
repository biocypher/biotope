"""Guided wizard backing ``biotope map``.

Rich-based, deterministic, manual-first. The wizard never auto-picks a record
set or fields; it enumerates options, validates, and previews after every
confirmed edit. Autosaves to the mapping file so sessions are interruptible.

Intent capture is folded directly into the wizard so users can also
add/remove ``required_entities`` / ``required_relations`` from the same flow.
Missing entity references encountered during relation editing trigger inline
entity creation so the session needs only one pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from biotope.croissant.mapping import (
    DatasetInspection,
    Mapping,
    inspect_dataset,
    preview_mapping,
    to_snake_case,
)
from biotope.croissant.mapping.defaults import intent_comment, unresolved_scaffold
from biotope.croissant.mapping.render import (
    build_inspector_appendix,
    render_mapping_with_appendix,
)
from biotope.croissant.spec import CroissantDatasetModel, FieldKind
from biotope.project_model import Project, find_project, resolve_project_path

console = Console()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def launch_wizard(*, croissant_arg: str | None, mapping_arg: Path | None) -> None:
    """Resolve sources, then run the wizard's main loop."""
    project_path, project = _resolve_project()
    croissant_path, mapping_path = _resolve_targets(croissant_arg, mapping_arg, project_path)

    from biotope.commands.map import _load_croissant  # avoid circular import at module load

    dataset = _load_croissant(str(croissant_path))
    datasets_location = _infer_datasets_location(croissant_path)
    inspection = inspect_dataset(
        dataset, datasets_location=datasets_location, preview_rows=3
    )

    draft = _load_or_init_draft(mapping_path, croissant_path, project)
    _autosave(mapping_path, draft, dataset, datasets_location, project)

    console.print(
        Panel(
            f"[bold]Project:[/bold] {project.name}\n"
            f"[bold]Croissant:[/bold] {croissant_path}\n"
            f"[bold]Mapping:[/bold] {mapping_path}",
            title="biotope map",
            border_style="cyan",
        )
    )

    # Intent capture on first run if empty
    if not (project.required_entities or project.required_relations):
        if Confirm.ask(
            "No entities or relations declared yet. Capture intent now?", default=True
        ):
            project = _intent_capture(project_path, project)
            draft = _sync_slots_from_intent(draft, project)
            _autosave(mapping_path, draft, dataset, datasets_location, project)

    _main_loop(
        project_path=project_path,
        project=project,
        mapping_path=mapping_path,
        croissant_path=croissant_path,
        dataset=dataset,
        datasets_location=datasets_location,
        inspection=inspection,
        draft=draft,
    )


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


def _resolve_project() -> tuple[Path, Project]:
    project_path = find_project()
    if project_path is None:
        console.print("❌ No project.yaml found. Run `biotope init <name>` first.")
        raise click.Abort
    return project_path, Project.load(project_path)


def _resolve_targets(
    croissant_arg: str | None,
    mapping_arg: Path | None,
    project_path: Path,
) -> tuple[Path, Path]:
    project_root = (
        project_path.parent.parent if project_path.parent.name == ".biotope" else project_path.parent
    )
    mappings_dir = project_root / "mappings"
    mappings_dir.mkdir(parents=True, exist_ok=True)

    if mapping_arg is not None:
        mapping_path = mapping_arg
        if not mapping_path.exists() and croissant_arg is None:
            console.print(f"❌ Mapping file not found: {mapping_path}")
            raise click.Abort
        if mapping_path.exists():
            data = yaml.safe_load(mapping_path.read_text()) or {}
            croissant_str = croissant_arg or data.get("croissant")
            if croissant_str is None:
                console.print("❌ Mapping file is missing the `croissant:` key.")
                raise click.Abort
            return Path(croissant_str), mapping_path

    if croissant_arg is None:
        croissant_arg = _pick_existing_resource(project_root)

    croissant_path = Path(croissant_arg).resolve()
    mapping_path = mappings_dir / f"{_mapping_stem(croissant_path)}.mapping.yaml"
    if mapping_arg is not None:
        mapping_path = mapping_arg
    return croissant_path, mapping_path


def _pick_existing_resource(project_root: Path) -> str:
    from biotope.commands.map import discover_croissants  # avoid circular import

    croissants = discover_croissants(project_root)
    croissants += sorted(project_root.glob("*.croissant.json"))
    mappings = sorted((project_root / "mappings").glob("*.mapping.yaml"))

    if not croissants and not mappings:
        _show_empty_state(project_root)
        raise click.Abort
    if len(croissants) == 1 and not mappings:
        return str(croissants[0])

    items: list[tuple[str, str, str]] = []
    for p in mappings:
        items.append(("mapping", str(p), "resume mapping"))
    for p in croissants:
        try:
            rel = p.relative_to(project_root)
        except ValueError:
            rel = p
        items.append(("croissant", str(p), f"new mapping for {rel}"))

    table = Table(title="What do you want to do?", show_lines=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Action")
    table.add_column("Path", style="dim")
    for i, (_, path, label) in enumerate(items, start=1):
        table.add_row(str(i), label, path)
    console.print(table)
    idx = IntPrompt.ask("Selection", default=1)
    kind, path, _ = items[max(1, min(idx, len(items))) - 1]
    if kind == "mapping":
        data = yaml.safe_load(Path(path).read_text()) or {}
        return data.get("croissant", path)
    return path


def _show_empty_state(project_root: Path) -> None:
    """Help text when neither data nor a mapping exists yet."""
    console.print(
        Panel(
            "No datasets have been ingested and no mapping exists yet.\n\n"
            "[bold]Two ways forward:[/bold]\n\n"
            "[bold cyan]1. Add data first (recommended):[/bold cyan]\n"
            "   biotope add <data_path> --license ... --creator ...\n"
            "   biotope map                # re-run; pick the dataset to map\n\n"
            "[bold cyan]2. Declare intent up-front (still need data later):[/bold cyan]\n"
            "   biotope map --entity gene --entity disease \\\n"
            "               --relation gene_in_disease\n"
            "   biotope add <data_path>\n"
            "   biotope map\n\n"
            "[dim]Once data is added, the per-directory Croissant JSON-LD lands at\n"
            ".biotope/datasets/<same-rel-path>.jsonld. You can also pass the\n"
            "data directory directly: [bold]biotope map -c <data_dir>[/bold].[/dim]",
            title=f"biotope map — empty project ({project_root.name})",
            border_style="yellow",
        )
    )


def _infer_datasets_location(croissant_path: str | Path) -> Path | None:
    path = Path(croissant_path).resolve()
    for parent in path.parents:
        if parent.name == "datasets" and parent.parent.name == ".biotope":
            return parent.parent.parent
    return path.parent


def _mapping_stem(path: Path) -> str:
    name = path.name
    for suffix in (".croissant.json", ".jsonld", ".json", ".yaml", ".yml"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


# ---------------------------------------------------------------------------
# Draft state — partial mapping as a mutable dict
# ---------------------------------------------------------------------------


def _load_or_init_draft(
    mapping_path: Path,
    croissant_path: Path,
    project: Project,
) -> dict[str, Any]:
    """Load an existing draft mapping or initialise a fresh unresolved scaffold."""
    if mapping_path.exists():
        data = yaml.safe_load(mapping_path.read_text()) or {}
        if "nodes" in data or "edges" in data:
            console.print(
                Panel(
                    "[red]Legacy `nodes`/`edges` mapping detected.[/red]\n"
                    "This wizard does not migrate legacy mappings. "
                    "Delete the file and re-run `biotope map` to start fresh.",
                    title=str(mapping_path),
                    border_style="red",
                )
            )
            raise click.Abort
        data.setdefault("croissant", str(croissant_path))
        return data

    scaffold = unresolved_scaffold(
        str(croissant_path),
        required_entities=project.required_entities,
        required_relations=project.required_relations,
    )
    return _mapping_to_dict(scaffold)


def _sync_slots_from_intent(draft: dict[str, Any], project: Project) -> dict[str, Any]:
    """Ensure every entity/relation declared in project.yaml has a slot in the draft."""
    entities = dict(draft.get("entities") or {})
    for raw in project.required_entities:
        key = to_snake_case(raw)
        entities.setdefault(key, {"scan": "row"})
    draft["entities"] = entities

    relations = dict(draft.get("relations") or {})
    for raw in project.required_relations:
        key = to_snake_case(raw)
        relations.setdefault(key, {"scan": "row"})
    draft["relations"] = relations
    return draft


def _mapping_to_dict(mapping: Mapping) -> dict[str, Any]:
    """Serialise a Mapping to a plain dict matching the YAML shape."""
    from biotope.croissant.mapping.render import _mapping_payload  # noqa: PLC0415

    return _mapping_payload(mapping)


def _validate_draft(draft: dict[str, Any]) -> Mapping | None:
    try:
        return Mapping.model_validate(draft)
    except ValidationError as exc:
        console.print(f"[yellow]ℹ partial state ({exc.error_count()} issue(s))[/yellow]")
        return None


def _autosave(
    mapping_path: Path,
    draft: dict[str, Any],
    dataset: CroissantDatasetModel,
    datasets_location: Path | None,
    project: Project,
) -> None:
    mapping = _validate_draft(draft)
    if mapping is None:
        # Save raw YAML even if validation fails so the user can fix manually.
        mapping_path.write_text(yaml.safe_dump(draft, sort_keys=False))
        return
    appendix = build_inspector_appendix(
        dataset,
        datasets_location=datasets_location,
        preview_rows=3,
    )
    comment = intent_comment(
        required_entities=project.required_entities,
        required_relations=project.required_relations,
        purpose=project.purpose,
    )
    mapping_path.write_text(
        render_mapping_with_appendix(mapping, appendix=appendix, intent_comment=comment)
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def _main_loop(
    *,
    project_path: Path,
    project: Project,
    mapping_path: Path,
    croissant_path: Path,
    dataset: CroissantDatasetModel,
    datasets_location: Path | None,
    inspection: DatasetInspection,
    draft: dict[str, Any],
) -> None:
    while True:
        _render_progress(draft, project)
        choice = _menu_choice(draft)
        if choice == "quit":
            console.print(f"💾 Saved to [cyan]{mapping_path}[/cyan]")
            return
        if choice == "intent":
            project = _intent_capture(project_path, project)
            draft = _sync_slots_from_intent(draft, project)
        elif choice == "preview":
            _show_preview(draft, dataset, datasets_location)
            continue
        elif choice.startswith("entity:"):
            key = choice.split(":", 1)[1]
            _edit_entity_slot(draft, key, inspection)
        elif choice.startswith("relation:"):
            key = choice.split(":", 1)[1]
            _edit_relation_slot(draft, key, inspection, project_path, project)
            # Relation editing may have added new entities; re-sync from project.
            project = Project.load(project_path)
        _autosave(mapping_path, draft, dataset, datasets_location, project)


def _render_progress(draft: dict[str, Any], project: Project) -> None:
    entities = draft.get("entities") or {}
    relations = draft.get("relations") or {}
    resolved_e = sum(1 for v in entities.values() if _entity_is_resolved(v))
    resolved_r = sum(1 for v in relations.values() if _relation_is_resolved(v))
    console.print(
        Panel(
            f"[bold]Entities:[/bold] {resolved_e}/{len(entities)} resolved\n"
            f"[bold]Relations:[/bold] {resolved_r}/{len(relations)} resolved\n"
            f"[bold]Purpose:[/bold] {project.purpose or '[dim](not set)[/dim]'}",
            title="Mapping progress",
            border_style="blue",
            expand=False,
        )
    )


def _menu_choice(draft: dict[str, Any]) -> str:
    entities = draft.get("entities") or {}
    relations = draft.get("relations") or {}

    items: list[tuple[str, str]] = []
    for key, val in entities.items():
        status = "✓" if _entity_is_resolved(val) else "○"
        items.append((f"entity:{key}", f"{status} entity   {key}"))
    for key, val in relations.items():
        status = "✓" if _relation_is_resolved(val) else "○"
        items.append((f"relation:{key}", f"{status} relation {key}"))
    items.append(("intent", "↳ open intent capture (add/remove entities and relations)"))
    items.append(("preview", "↳ show preview"))
    items.append(("quit", "↳ save and quit"))

    table = Table(title="Choose a slot", show_lines=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Action")
    for i, (_, label) in enumerate(items, start=1):
        table.add_row(str(i), label)
    console.print(table)

    default = next(
        (i for i, (code, _) in enumerate(items, start=1) if code.startswith(("entity:", "relation:"))
         and not _slot_resolved(draft, code)),
        len(items),
    )
    idx = IntPrompt.ask("Selection", default=default)
    return items[max(1, min(idx, len(items))) - 1][0]


def _slot_resolved(draft: dict[str, Any], code: str) -> bool:
    kind, key = code.split(":", 1)
    if kind == "entity":
        return _entity_is_resolved((draft.get("entities") or {}).get(key, {}))
    if kind == "relation":
        return _relation_is_resolved((draft.get("relations") or {}).get(key, {}))
    return True


def _entity_is_resolved(entity: dict[str, Any]) -> bool:
    return bool(entity.get("record_set")) and bool(entity.get("id"))


def _relation_is_resolved(relation: dict[str, Any]) -> bool:
    return (
        bool(relation.get("record_set"))
        and bool(relation.get("source"))
        and bool((relation.get("source") or {}).get("entity"))
        and bool(relation.get("target"))
        and bool((relation.get("target") or {}).get("entity"))
    )


# ---------------------------------------------------------------------------
# Intent capture
# ---------------------------------------------------------------------------


def _intent_capture(project_path: Path, project: Project) -> Project:
    console.print(
        Panel(
            f"purpose: {project.purpose or '(empty)'}\n"
            f"entities: {', '.join(project.required_entities) or '(none)'}\n"
            f"relations: {', '.join(project.required_relations) or '(none)'}",
            title="Current intent",
            border_style="cyan",
            expand=False,
        )
    )
    data = project.model_dump()

    if Confirm.ask("Update purpose?", default=False):
        data["purpose"] = Prompt.ask("Purpose", default=project.purpose or "")

    while Confirm.ask("Add an entity?", default=not data["required_entities"]):
        name = Prompt.ask("Entity name (free text)").strip()
        if name:
            data["required_entities"].append(name)

    if data["required_entities"] and Confirm.ask("Remove an entity?", default=False):
        idx = _pick_index("Entity to remove", data["required_entities"])
        if idx is not None:
            removed = data["required_entities"].pop(idx)
            console.print(f"[yellow]Removed entity:[/yellow] {removed}")

    while Confirm.ask("Add a relation?", default=not data["required_relations"]):
        name = Prompt.ask("Relation name (free text)").strip()
        if name:
            data["required_relations"].append(name)

    if data["required_relations"] and Confirm.ask("Remove a relation?", default=False):
        idx = _pick_index("Relation to remove", data["required_relations"])
        if idx is not None:
            removed = data["required_relations"].pop(idx)
            console.print(f"[yellow]Removed relation:[/yellow] {removed}")

    updated = Project.model_validate(data)
    updated.dump(project_path)
    console.print(f"💾 Saved intent to [cyan]{project_path}[/cyan]")
    return updated


def _pick_index(prompt: str, items: list[str]) -> int | None:
    if not items:
        return None
    for i, item in enumerate(items, start=1):
        console.print(f"  {i}. {item}")
    raw = Prompt.ask(prompt, default="")
    if not raw.strip():
        return None
    try:
        idx = int(raw) - 1
    except ValueError:
        return None
    if 0 <= idx < len(items):
        return idx
    return None


# ---------------------------------------------------------------------------
# Entity slot editor
# ---------------------------------------------------------------------------


def _edit_entity_slot(
    draft: dict[str, Any],
    key: str,
    inspection: DatasetInspection,
) -> None:
    entities = dict(draft.get("entities") or {})
    entity = dict(entities.get(key) or {})
    console.print(Panel(f"Editing entity: [bold]{key}[/bold]", border_style="cyan", expand=False))

    rs_name = _pick_record_set(inspection, entity.get("record_set"))
    if rs_name is None:
        return
    entity["record_set"] = rs_name
    rs = inspection.by_name(rs_name)
    assert rs is not None

    entity["scan"] = _pick_scan(rs, entity.get("scan"))

    namespace = entity.get("namespace")
    new_namespace = Prompt.ask(
        "Namespace (optional, e.g. 'ensembl', 'mondo'; blank to derive)",
        default=namespace or "",
    )
    if new_namespace.strip():
        entity["namespace"] = new_namespace.strip()
    elif "namespace" in entity:
        del entity["namespace"]

    entity["id"] = _pick_id_selector(
        rs,
        draft.get("ids") or {},
        existing=entity.get("id"),
        propose_promotion=True,
        draft=draft,
    )

    entity["properties"] = _pick_properties(rs, entity.get("properties") or {})

    entities[key] = entity
    draft["entities"] = entities


def _pick_record_set(inspection: DatasetInspection, current: str | None) -> str | None:
    if not inspection.record_sets:
        console.print("[red]No record sets in this Croissant file.[/red]")
        return None
    table = Table(title="Record sets", show_lines=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Fields", style="dim")
    for i, rs in enumerate(inspection.record_sets, start=1):
        marker = " *" if rs.name == current else ""
        table.add_row(
            f"{i}{marker}",
            rs.name,
            (rs.description or "")[:60],
            ", ".join(f.name for f in rs.fields[:6]) + (" …" if len(rs.fields) > 6 else ""),
        )
    console.print(table)
    default_idx = next(
        (i for i, rs in enumerate(inspection.record_sets, start=1) if rs.name == current),
        1,
    )
    idx = IntPrompt.ask("Pick record set", default=default_idx)
    return inspection.record_sets[max(1, min(idx, len(inspection.record_sets))) - 1].name


def _pick_scan(rs, current: Any) -> Any:
    if not rs.array_fields:
        return "row"
    current_explode = (
        current.get("explode") if isinstance(current, dict) and "explode" in current else None
    )
    console.print(
        f"[dim]Explode-eligible arrays:[/dim] {', '.join(rs.array_fields)}"
    )
    choice = Prompt.ask(
        "Scan kind: [r]ow or [e]xplode <array>",
        choices=["r", "e"],
        default="e" if current_explode else "r",
    )
    if choice == "r":
        return "row"
    field = _pick_from(
        rs.array_fields,
        prompt="Explode field",
        default=current_explode or rs.array_fields[0],
    )
    return {"explode": field}


def _pick_id_selector(
    rs,
    ids: dict[str, Any],
    *,
    existing: Any,
    propose_promotion: bool,
    draft: dict[str, Any],
) -> dict[str, Any]:
    while True:
        actions = ["field"]
        if ids:
            actions.append("use")
        actions.append("hash_id")
        actions.append("promote")
        console.print(
            "[dim]ID selector actions:[/dim] "
            f"{', '.join(actions)} (current: {existing or 'unset'})"
        )
        action = Prompt.ask(
            "Choose action",
            choices=actions,
            default="use" if isinstance(existing, dict) and existing.get("use") else "field",
        )
        if action == "field":
            field = _pick_from(
                [f.name for f in rs.fields],
                prompt="ID field",
                default=(existing or {}).get("field"),
            )
            transform = Prompt.ask(
                "Transform", choices=["passthrough", "as_curie"], default="passthrough"
            )
            selector: dict[str, Any] = {"field": field}
            if transform != "passthrough":
                selector["transform"] = transform
                prefix = Prompt.ask("CURIE prefix (e.g. 'ensembl')")
                selector["args"] = {"prefix": prefix}
            return selector
        if action == "use":
            name = _pick_from(list(ids), prompt="Named id to reuse")
            return {"use": name}
        if action == "hash_id":
            fields_str = Prompt.ask(
                "Fields to hash (comma-separated)",
                default=",".join((existing or {}).get("args", {}).get("fields", [rs.fields[0].name])),
            )
            fields = [f.strip() for f in fields_str.split(",") if f.strip()]
            prefix = Prompt.ask("Hash prefix (optional)", default="")
            args: dict[str, Any] = {"fields": fields}
            if prefix.strip():
                args["prefix"] = prefix.strip()
            return {"transform": "hash_id", "args": args}
        if action == "promote":
            # Build a draft selector first, then store it under ids:
            sub = _pick_id_selector(
                rs, ids, existing=existing, propose_promotion=False, draft=draft
            )
            name = Prompt.ask("Name for the new reusable id (snake_case)")
            ids_block = dict(draft.get("ids") or {})
            ids_block[to_snake_case(name)] = sub
            draft["ids"] = ids_block
            return {"use": to_snake_case(name)}


def _pick_properties(rs, current: dict[str, Any]) -> dict[str, Any]:
    field_names = [f.name for f in rs.fields if f.kind != FieldKind.STRUCT.value]
    if not field_names:
        return current
    selected_names = list(current.keys())
    console.print(f"[dim]Available fields:[/dim] {', '.join(field_names)}")
    raw = Prompt.ask(
        "Property fields (comma-separated; blank to keep current)",
        default=",".join(selected_names),
    )
    chosen = [n.strip() for n in raw.split(",") if n.strip()]
    out: dict[str, Any] = {}
    for name in chosen:
        if name in current:
            out[name] = current[name]
        else:
            out[name] = name  # string shorthand: field name
    return out


# ---------------------------------------------------------------------------
# Relation slot editor
# ---------------------------------------------------------------------------


def _edit_relation_slot(
    draft: dict[str, Any],
    key: str,
    inspection: DatasetInspection,
    project_path: Path,
    project: Project,
) -> None:
    relations = dict(draft.get("relations") or {})
    relation = dict(relations.get(key) or {})
    console.print(Panel(f"Editing relation: [bold]{key}[/bold]", border_style="cyan", expand=False))

    rs_name = _pick_record_set(inspection, relation.get("record_set"))
    if rs_name is None:
        return
    relation["record_set"] = rs_name
    rs = inspection.by_name(rs_name)
    assert rs is not None

    relation["scan"] = _pick_scan(rs, relation.get("scan"))

    for side in ("source", "target"):
        relation[side] = _pick_endpoint(
            rs,
            draft,
            project_path,
            project,
            existing=relation.get(side),
            label=side,
            inspection=inspection,
        )
        # Re-read project after potential inline entity creation
        project = Project.load(project_path)

    relation["properties"] = _pick_properties(rs, relation.get("properties") or {})

    relations[key] = relation
    draft["relations"] = relations


def _pick_endpoint(
    rs,
    draft: dict[str, Any],
    project_path: Path,
    project: Project,
    *,
    existing: Any,
    label: str,
    inspection: DatasetInspection,
) -> dict[str, Any]:
    entities = list((draft.get("entities") or {}).keys())
    console.print(f"[dim]Endpoint `{label}` — pick referenced entity[/dim]")
    if entities:
        for i, key in enumerate(entities, start=1):
            console.print(f"  {i}. {key}")
        console.print(f"  {len(entities) + 1}. + create a new entity inline")
    else:
        console.print("  (no entities defined yet — you'll create one now)")
        entities = []
    pick = IntPrompt.ask(
        "Selection",
        default=(
            entities.index((existing or {}).get("entity")) + 1
            if (existing or {}).get("entity") in entities
            else len(entities) + 1
        ),
    )
    if pick == len(entities) + 1 or not entities:
        new_key = _create_entity_inline(draft, inspection, project_path, project)
        entity_ref = new_key
    else:
        entity_ref = entities[max(1, min(pick, len(entities))) - 1]

    # Now pick the selector for the value on this row.
    selector = _pick_id_selector(
        rs,
        draft.get("ids") or {},
        existing=existing,
        propose_promotion=True,
        draft=draft,
    )
    selector["entity"] = entity_ref
    # Reorder so `entity` comes first in the YAML.
    return {"entity": entity_ref, **{k: v for k, v in selector.items() if k != "entity"}}


def _create_entity_inline(
    draft: dict[str, Any],
    inspection: DatasetInspection,
    project_path: Path,
    project: Project,
) -> str:
    raw_name = Prompt.ask("New entity name (free text)")
    key = to_snake_case(raw_name)
    console.print(f"[green]Creating entity[/green] [bold]{key}[/bold]")

    # Append to project.yaml:required_entities (preserving original phrasing)
    if raw_name not in project.required_entities:
        data = project.model_dump()
        data["required_entities"] = list(data["required_entities"]) + [raw_name]
        Project.model_validate(data).dump(project_path)

    entities = dict(draft.get("entities") or {})
    entities.setdefault(key, {"scan": "row"})
    draft["entities"] = entities

    # Drop into the entity editor for the new key
    _edit_entity_slot(draft, key, inspection)
    return key


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def _show_preview(
    draft: dict[str, Any],
    dataset: CroissantDatasetModel,
    datasets_location: Path | None,
) -> None:
    mapping = _validate_draft(draft)
    if mapping is None:
        console.print("[yellow]Cannot preview: draft is not valid YAML for a mapping.[/yellow]")
        return
    result = preview_mapping(
        mapping, dataset, datasets_location=datasets_location, sample_rows=3
    )
    if result.unresolved_slots:
        console.print(
            Panel(
                "\n".join(f"○ {s}" for s in result.unresolved_slots),
                title="Unresolved",
                border_style="yellow",
                expand=False,
            )
        )
    if result.findings:
        lines = [f"[{f.severity}] {f.path}: {f.message}" for f in result.findings]
        console.print(
            Panel("\n".join(lines), title="Validation", border_style="red", expand=False)
        )
    if result.entities or result.relations:
        sections: list[str] = []
        for e in result.entities:
            sections.append(
                f"entity {e.key}: schema_term={e.schema_term}, namespace={e.namespace}, "
                f"properties={list(e.properties)}"
            )
        for r in result.relations:
            sections.append(
                f"relation {r.key}: {r.source} -> {r.target}, properties={list(r.properties)}"
            )
        console.print(
            Panel("\n".join(sections), title="Projected schema", border_style="cyan", expand=False)
        )


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def _pick_from(
    options: list[str],
    *,
    prompt: str,
    default: str | None = None,
) -> str:
    if not options:
        return Prompt.ask(prompt, default=default or "")
    for i, name in enumerate(options, start=1):
        marker = " *" if name == default else ""
        console.print(f"  {i}{marker}. {name}")
    default_idx = options.index(default) + 1 if default in options else 1
    idx = IntPrompt.ask(prompt, default=default_idx)
    return options[max(1, min(idx, len(options))) - 1]
