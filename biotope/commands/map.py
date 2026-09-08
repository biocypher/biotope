"""``biotope map`` — semantic mapping authoring commands.

* ``biotope map`` (bare) launches the guided wizard, unless any intent flag
  (``--purpose``, ``--entity``, ``--relation``, ``--source``, ``--notes``,
  ``--clear-*``, ``--show``) is present, in which case it applies the edit
  non-interactively and exits.
* ``biotope map inspect <croissant>`` — deterministic Croissant/data inspector.
* ``biotope map scaffold <croissant>`` — non-interactive unresolved scaffold.
* ``biotope map preview [<mapping>]`` — structural mapping summary.

All semantic decisions are made by the user or the editing agent. The CLI
never auto-picks record sets or fields.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from biotope.croissant.acquisition import infer_datasets_location
from biotope.croissant.api import scaffold_mapping
from biotope.croissant.mapping import (
    Mapping,
    MultiMappingPreview,
    aggregate_previews,
    inspect_dataset,
    load_mapping,
    preview_mapping,
    render_inspection_text,
)
from biotope.croissant.mapping.preview import VALIDATION_SCOPE
from biotope.croissant.spec import CroissantDatasetModel, load_from_path, load_from_url
from biotope.project_model import Project, find_project


console = Console()


# ---------------------------------------------------------------------------
# Group entry point: bare `biotope map`
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True, name="map")
@click.option(
    "--croissant",
    "-c",
    "croissant",
    type=str,
    default=None,
    help="Path to a Croissant JSON-LD file for the wizard to operate on.",
)
@click.option("--mapping", "mapping_path", type=click.Path(path_type=Path), default=None)
@click.option("--purpose", "-p", type=str, default=None, help="Replace the project's purpose statement.")
@click.option("--entity", "-e", "entities", multiple=True, help="Add to required_entities. Repeatable.")
@click.option("--relation", "-r", "relations", multiple=True, help="Add to required_relations. Repeatable.")
@click.option("--source", "-s", "sources", multiple=True, help="Add to data_sources. Repeatable.")
@click.option("--notes", type=str, default=None, help="Replace the notes field.")
@click.option("--clear-entities", is_flag=True, help="Empty required_entities before adding.")
@click.option("--clear-relations", is_flag=True, help="Empty required_relations before adding.")
@click.option("--clear-sources", is_flag=True, help="Empty data_sources before adding.")
@click.option("--show", is_flag=True, help="Print intent + mapping progress and exit.")
@click.pass_context
def map_group(
    ctx: click.Context,
    croissant: str | None,
    mapping_path: Path | None,
    purpose: str | None,
    entities: tuple[str, ...],
    relations: tuple[str, ...],
    sources: tuple[str, ...],
    notes: str | None,
    clear_entities: bool,
    clear_relations: bool,
    clear_sources: bool,
    show: bool,
) -> None:
    """Semantic mapping for a Croissant dataset."""
    if ctx.invoked_subcommand is not None:
        return

    intent_flags_present = any(
        [
            purpose is not None,
            notes is not None,
            entities,
            relations,
            sources,
            clear_entities,
            clear_relations,
            clear_sources,
            show,
        ],
    )

    if intent_flags_present:
        _apply_intent_flags(
            purpose=purpose,
            entities=entities,
            relations=relations,
            sources=sources,
            notes=notes,
            clear_entities=clear_entities,
            clear_relations=clear_relations,
            clear_sources=clear_sources,
            show=show,
        )
        return

    from biotope.commands.map_wizard import launch_wizard

    launch_wizard(croissant_arg=croissant, mapping_arg=mapping_path)


def _apply_intent_flags(
    *,
    purpose: str | None,
    entities: tuple[str, ...],
    relations: tuple[str, ...],
    sources: tuple[str, ...],
    notes: str | None,
    clear_entities: bool,
    clear_relations: bool,
    clear_sources: bool,
    show: bool,
) -> None:
    project_path = find_project()
    if project_path is None:
        click.echo("❌ No project.yaml found. Run `biotope init <name>` first.")
        raise click.Abort

    project = Project.load(project_path)

    if show and not any([purpose, notes, entities, relations, sources, clear_entities, clear_relations, clear_sources]):
        _render_intent(project_path, project)
        return

    data = project.model_dump()
    _warn_destructive_clears(
        project,
        clear_entities=clear_entities,
        clear_relations=clear_relations,
        clear_sources=clear_sources,
    )
    if purpose is not None:
        data["purpose"] = purpose
    if notes is not None:
        data["notes"] = notes
    if clear_entities:
        data["required_entities"] = []
    if entities:
        data["required_entities"] = list(data["required_entities"]) + list(entities)
    if clear_relations:
        data["required_relations"] = []
    if relations:
        data["required_relations"] = list(data["required_relations"]) + list(relations)
    if clear_sources:
        data["data_sources"] = []
    if sources:
        data["data_sources"] = list(data["data_sources"]) + list(sources)

    updated = Project.model_validate(data)
    updated.dump(project_path)
    console.print(f"✅ Updated [cyan]{project_path}[/cyan]")
    _render_intent(project_path, updated)


def _warn_destructive_clears(
    project: Project,
    *,
    clear_entities: bool,
    clear_relations: bool,
    clear_sources: bool,
) -> None:
    """Print a Rich warning panel when a `--clear-*` flag drops user content.

    The flag still works — the friction is purely informational so that an
    agent (or human) running the command sees that they are about to erase
    the project's declared intent. The schema-is-a-contract rule forbids doing
    this without the user's explicit instruction.
    """
    sections: list[str] = []
    if clear_entities and project.required_entities:
        joined = "\n".join(f"  • {e}" for e in project.required_entities)
        sections.append(f"[bold]required_entities[/bold] ({len(project.required_entities)} item(s)):\n{joined}")
    if clear_relations and project.required_relations:
        joined = "\n".join(f"  • {r}" for r in project.required_relations)
        sections.append(f"[bold]required_relations[/bold] ({len(project.required_relations)} item(s)):\n{joined}")
    if clear_sources and project.data_sources:
        joined = "\n".join(f"  • {s}" for s in project.data_sources)
        sections.append(f"[bold]data_sources[/bold] ({len(project.data_sources)} item(s)):\n{joined}")
    if not sections:
        return
    body = (
        "About to erase the following from the project's declared intent.\n"
        "If the user did not explicitly ask for this, stop and confirm first.\n\n" + "\n\n".join(sections)
    )
    console.print(
        Panel(
            body,
            title="⚠  Destructive: --clear-* will drop user-declared intent",
            border_style="red",
            expand=False,
        )
    )


def _render_intent(project_path: Path, project: Project) -> None:
    lines = [
        f"[bold]name:[/bold] {project.name}",
        f"[bold]purpose:[/bold] {project.purpose or '[dim](not set)[/dim]'}",
        f"[bold]required entities:[/bold] {', '.join(project.required_entities) or '[dim](none)[/dim]'}",
        f"[bold]required relations:[/bold] {', '.join(project.required_relations) or '[dim](none)[/dim]'}",
    ]
    if project.data_sources:
        lines.append(f"[bold]data sources:[/bold] {', '.join(project.data_sources)}")
    if project.notes:
        lines.append(f"[bold]notes:[/bold] {project.notes}")
    console.print(Panel("\n".join(lines), title=str(project_path), border_style="cyan", expand=False))


# ---------------------------------------------------------------------------
# `biotope map inspect`
# ---------------------------------------------------------------------------


@map_group.command()
@click.argument("croissant", type=str)
@click.option("--json", "as_json", is_flag=True, help="Emit a machine-readable JSON inspection.")
def inspect(croissant: str, as_json: bool) -> None:
    """Inspect a Croissant dataset deterministically."""
    dataset = _load_croissant(croissant)
    datasets_location = infer_datasets_location(croissant)
    _warn_if_manifest_drifted(croissant, datasets_location)
    inspection = inspect_dataset(
        dataset,
    )
    if as_json:
        click.echo(json.dumps(inspection.to_json(), indent=2, default=str))
        return
    click.echo(render_inspection_text(inspection))


# ---------------------------------------------------------------------------
# `biotope map scaffold`
# ---------------------------------------------------------------------------


@map_group.command()
@click.argument("croissant", type=str)
@click.option(
    "--out",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Where to write the scaffold. Default: mappings/<stem>.mapping.yaml under the project root.",
)
@click.option("--stdout", "to_stdout", is_flag=True, help="Print to stdout instead of writing a file.")
def scaffold(croissant: str, out: Path | None, to_stdout: bool) -> None:
    """Generate an unresolved semantic mapping scaffold for a Croissant file."""
    if out is not None and to_stdout:
        raise click.UsageError("Choose either --out or --stdout, not both.")

    _load_croissant(croissant)  # validate up front with friendly errors
    _warn_if_manifest_drifted(croissant, infer_datasets_location(croissant))

    target = out
    if target is None and not to_stdout:
        target = _default_output_path(croissant)
        if target is not None:
            target.parent.mkdir(parents=True, exist_ok=True)

    project = _load_project_optional()
    result = scaffold_mapping(
        croissant,
        required_entities=list(project.required_entities) if project else [],
        required_relations=list(project.required_relations) if project else [],
        purpose=project.purpose if project else None,
        write_to=target,
    )
    if target:
        console.print(f"✅ Wrote {target}")
        unresolved = result.get("unresolved") or []
        if unresolved:
            console.print(
                f"[yellow]ℹ[/yellow] {len(unresolved)} unresolved slot(s); run [bold]biotope map[/bold] to resolve."
            )
    else:
        click.echo(result["yaml"], nl=False)


# ---------------------------------------------------------------------------
# `biotope map preview`
# ---------------------------------------------------------------------------


@map_group.command()
@click.argument(
    "mapping_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
)
@click.option("--json", "as_json", is_flag=True, help="Emit a machine-readable JSON preview.")
def preview(mapping_path: Path | None, as_json: bool) -> None:
    """Check mapping definitions and summarize the target schema. No values are loaded.

    With no path, previews every mapping under the project's ``mappings/`` dir
    (multi-mapping projects are the norm); pass an explicit path to preview
    just one.
    """
    if mapping_path is not None:
        paths = [mapping_path]
    else:
        paths = _discover_project_mappings()
        if not paths:
            click.echo("❌ No mapping file found. Pass a path or run `biotope map scaffold` first.")
            raise click.Abort

    previews: list[tuple[Path, Mapping, object]] = []
    for path in paths:
        mapping = load_mapping(path)
        dataset = _load_croissant(mapping.croissant)
        datasets_location = infer_datasets_location(mapping.croissant)
        _warn_if_manifest_drifted(mapping.croissant, datasets_location)
        result = preview_mapping(
            mapping,
            dataset,
        )
        previews.append((path, mapping, result))

    aggregated = aggregate_previews([(path.name, result) for path, _, result in previews])
    invalid = any(
        result.unresolved_slots or any(f.severity == "error" for f in result.findings) for _, _, result in previews
    )

    if as_json:
        payload = {
            "validation_scope": VALIDATION_SCOPE,
            "global": aggregated.to_json(),
            "mappings": {path.name: result.to_json() for path, _, result in previews},
        }
        click.echo(json.dumps(payload, indent=2, default=str))
        if invalid:
            raise click.exceptions.Exit(1)
        return

    _render_global_schema_rich(aggregated)
    _render_slot_resolution_rich(aggregated, [path.name for path, _, _ in previews])
    _render_global_findings_rich(aggregated)
    for path, mapping, result in previews:
        _render_per_file_panels(path, result)
    click.echo(f"Structural checks {'need attention' if invalid else 'passed'}: {VALIDATION_SCOPE}.")
    if invalid:
        raise click.exceptions.Exit(1)


# ---------------------------------------------------------------------------
# `biotope map defer-relation` / `undefer-relation`
# ---------------------------------------------------------------------------


@map_group.command(name="defer-relation")
@click.argument("mapping_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("relation_name", type=str)
def defer_relation(mapping_path: Path, relation_name: str) -> None:
    """Mark a declared relation as unsupported by the available data.

    A deferred relation records a known gap in the proposed mapping.
    Use ``undefer-relation`` to reverse.
    """
    _set_relation_deferred(mapping_path, relation_name, deferred=True)
    console.print(f"✅ Marked relations.{relation_name} as deferred in [cyan]{mapping_path}[/cyan]")


@map_group.command(name="undefer-relation")
@click.argument("mapping_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("relation_name", type=str)
def undefer_relation(mapping_path: Path, relation_name: str) -> None:
    """Reverse a previous ``defer-relation``."""
    _set_relation_deferred(mapping_path, relation_name, deferred=False)
    console.print(f"✅ Cleared deferred on relations.{relation_name} in [cyan]{mapping_path}[/cyan]")


def _set_relation_deferred(mapping_path: Path, relation_name: str, *, deferred: bool) -> None:
    from biotope.croissant.mapping.loader import set_relation_deferred

    mapping = load_mapping(mapping_path)
    if relation_name not in mapping.relations:
        known = ", ".join(sorted(mapping.relations)) or "(none declared)"
        raise click.UsageError(f"Unknown relation {relation_name!r}. Known relations: {known}")
    set_relation_deferred(mapping, mapping_path, relation_name, deferred=deferred)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _warn_if_manifest_drifted(croissant_path: str, datasets_location: Path | None) -> None:
    """Print a stderr warning when data under ``datasets_location`` looks newer
    than the Croissant manifest — a mapping can't see columns added since the
    last bake. Printed to stderr so it never pollutes ``--json`` output."""
    if datasets_location is None:
        return
    from biotope.croissant.acquisition import detect_manifest_drift

    drifted = detect_manifest_drift(croissant_path, datasets_location)
    if not drifted:
        return
    sample = ", ".join(p.name for p in drifted[:3])
    more = f" (+{len(drifted) - 3} more)" if len(drifted) > 3 else ""
    click.echo(
        f"⚠️  {len(drifted)} file(s) under {datasets_location} are newer than "
        f"this Croissant manifest: {sample}{more}. If columns changed, "
        "re-run `biotope add --rebake <dir>` before mapping.",
        err=True,
    )


def _load_croissant(path: str) -> CroissantDatasetModel:
    """Load a Croissant JSON-LD file with a friendly error for common mistakes.

    Accepts three input shapes:

    * a Croissant JSON-LD path or URL (canonical form),
    * a `.biotope.yaml` annotate scaffold path (suggests the right file),
    * a *data directory* that was previously ingested via ``biotope add`` —
      resolved to the canonical ``.biotope/datasets/<rel>.jsonld`` automatically.
    """
    if path.startswith(("http://", "https://")):
        try:
            return load_from_url(path)
        except Exception as exc:
            console.print(f"❌ Could not load Croissant file from URL: [cyan]{path}[/cyan]\n   {exc}")
            raise click.Abort from exc

    p = Path(path)
    if not p.exists():
        console.print(f"❌ Croissant file not found: [cyan]{path}[/cyan]")
        raise click.Abort

    if p.is_dir():
        resolved = _resolve_data_dir_to_croissant(p)
        if resolved is None:
            console.print(
                Panel(
                    f"[cyan]{path}[/cyan] is a directory but no Croissant metadata has been "
                    f"generated for it.\n"
                    f"Run [bold]biotope add {path}[/bold] first; the Croissant file will land at "
                    f"[cyan].biotope/datasets/<...>.jsonld[/cyan].",
                    title="No Croissant for this directory",
                    border_style="red",
                )
            )
            raise click.Abort
        path = str(resolved)
        p = resolved

    suffix = p.name.lower()
    if suffix.endswith((".biotope.yaml", ".biotope.yml")) or p.name == ".biotope.yaml":
        suggestion = _suggest_croissant_jsonld(p)
        console.print(
            Panel(
                "This is a [yellow]biotope annotate scaffold[/yellow], not a Croissant JSON-LD file.\n"
                "`biotope map` expects the Croissant metadata for a dataset, which lives under "
                "[cyan].biotope/datasets/[/cyan].\n\n"
                + (
                    f"Try:  [bold]biotope map -c {suggestion}[/bold]"
                    if suggestion
                    else "Run [bold]biotope add <data>[/bold] first to generate the Croissant file under "
                    "[cyan].biotope/datasets/[/cyan]."
                ),
                title=str(p),
                border_style="red",
            )
        )
        raise click.Abort
    if suffix.endswith((".yaml", ".yml")):
        console.print(
            f"❌ [cyan]{path}[/cyan] looks like YAML, but Croissant metadata is JSON-LD.\n"
            "   Pass a Croissant JSON file from [cyan].biotope/datasets/[/cyan]."
        )
        raise click.Abort

    try:
        return load_from_path(path)
    except ValidationError as exc:
        console.print(
            Panel(
                f"[cyan]{path}[/cyan] is not a valid Croissant JSON-LD file.\n\n"
                f"Underlying error: {exc.errors()[0].get('msg', exc)}\n\n"
                "Pass a Croissant file from [cyan].biotope/datasets/[/cyan] (created by "
                "`biotope add`).",
                title="Invalid Croissant file",
                border_style="red",
            )
        )
        raise click.Abort from exc


def _resolve_data_dir_to_croissant(data_dir: Path) -> Path | None:
    """Given a data directory, return its canonical Croissant JSON-LD if it exists.

    ``biotope add <data_dir>`` writes the per-directory Croissant at
    ``.biotope/datasets/<same-relative-path>.jsonld``. We resolve that path and
    also fall back to searching for jsonld files mirrored under that subtree.
    """
    project_root = _project_root_from_cwd()
    if project_root is None:
        return None
    try:
        rel = data_dir.resolve().relative_to(project_root.resolve())
    except ValueError:
        return None
    datasets_root = project_root / ".biotope" / "datasets"
    canonical = datasets_root / f"{rel}.jsonld"
    if canonical.is_file():
        return canonical
    nested = sorted((datasets_root / rel).rglob("*.jsonld")) + sorted((datasets_root / rel).rglob("*.croissant.json"))
    return nested[0] if nested else None


def discover_croissants(project_root: Path) -> list[Path]:
    """Return all Croissant metadata files under a project's ``.biotope/datasets/``.

    Looks for both ``*.jsonld`` (baker output) and ``*.croissant.json`` (legacy /
    user-supplied) shapes.
    """
    datasets_root = project_root / ".biotope" / "datasets"
    if not datasets_root.is_dir():
        return []
    files = sorted(datasets_root.rglob("*.jsonld")) + sorted(datasets_root.rglob("*.croissant.json"))
    # Stable de-dup while preserving order.
    seen: set[Path] = set()
    out: list[Path] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _suggest_croissant_jsonld(annotate_scaffold: Path) -> str | None:
    """Given a `.biotope.yaml` scaffold path, guess where its Croissant JSON-LD lives.

    `biotope add` writes the per-directory Croissant JSON-LD at
    ``.biotope/datasets/<same-relative-path>.jsonld`` — *a file named after the
    directory*, not a directory containing per-file jsonlds. We try that
    canonical form first, then fall back to a broader glob.
    """
    project_root = _project_root_from_cwd()
    if project_root is None:
        return None
    datasets_root = project_root / ".biotope" / "datasets"
    if not datasets_root.is_dir():
        return None
    try:
        rel = annotate_scaffold.resolve().parent.relative_to(project_root.resolve())
    except ValueError:
        rel = None

    candidates: list[Path] = []
    if rel is not None:
        canonical = datasets_root / f"{rel}.jsonld"
        if canonical.is_file():
            candidates.append(canonical)
        candidates += sorted((datasets_root / rel).rglob("*.jsonld"))
        candidates += sorted((datasets_root / rel).rglob("*.croissant.json"))
    if not candidates:
        candidates = sorted(datasets_root.rglob("*.jsonld")) + sorted(datasets_root.rglob("*.croissant.json"))
    if not candidates:
        return None
    try:
        return str(candidates[0].relative_to(project_root))
    except ValueError:
        return str(candidates[0])


def _load_project_optional() -> Project | None:
    project_path = find_project()
    if project_path is None:
        return None
    try:
        return Project.load(project_path)
    except Exception:
        return None


def _default_output_path(croissant_path: str) -> Path | None:
    if croissant_path.startswith(("http://", "https://")):
        return None
    path = Path(croissant_path).resolve()
    project_root = _project_root_from_croissant_path(path) or _project_root_from_cwd()
    if project_root is None:
        return None
    return project_root / "mappings" / f"{_mapping_stem(path)}.mapping.yaml"


def _project_root_from_croissant_path(path: Path) -> Path | None:
    for parent in path.parents:
        if parent.name == "datasets" and parent.parent.name == ".biotope":
            return parent.parent.parent
    return None


def _project_root_from_cwd() -> Path | None:
    project_path = find_project()
    if project_path is None:
        return None
    return project_path.parent.parent if project_path.parent.name == ".biotope" else project_path.parent


def _mapping_stem(path: Path) -> str:
    name = path.name
    for suffix in (".croissant.json", ".jsonld", ".json", ".yaml", ".yml"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _discover_single_mapping() -> Path | None:
    project_root = _project_root_from_cwd()
    if project_root is None:
        return None
    mappings_dir = project_root / "mappings"
    if not mappings_dir.is_dir():
        return None
    candidates = sorted(mappings_dir.glob("*.mapping.yaml")) + sorted(mappings_dir.glob("*.mapping.yml"))
    return candidates[0] if len(candidates) == 1 else None


def _discover_project_mappings() -> list[Path]:
    """Return project mapping definitions, preferring explicit mapping suffixes."""
    from biotope.croissant.mapping.loader import discover_mapping_paths

    project_root = _project_root_from_cwd()
    if project_root is None:
        return []
    mappings_dir = project_root / "mappings"
    if not mappings_dir.is_dir():
        return []
    return discover_mapping_paths(mappings_dir)


def _render_global_schema_rich(agg: MultiMappingPreview) -> None:
    """Render the merged KG topology across all mapping files."""
    if not (agg.entities or agg.relations):
        console.print(
            Panel(
                "[dim]No resolved entities or relations yet. Run [bold]biotope map[/bold] to "
                "fill in the mapping files.[/dim]",
                title="KG schema",
                border_style="dim",
                expand=False,
            )
        )
        return

    sections: list[str] = []
    if agg.entities:
        sections.append("[bold]Entities:[/bold]")
        for e in agg.entities:
            label = e.schema_term if e.schema_term == e.key else f"{e.key} (label: {e.schema_term})"
            props = ", ".join(f"{k}:{v}" for k, v in e.properties.items()) or "(none)"
            sources = ", ".join(e.sources)
            sections.append(f"  {label}   namespace: {e.namespace}")
            sections.append(f"    properties: {props}")
            sections.append(f"    [dim]from: {sources}[/dim]")
    if agg.relations:
        if sections:
            sections.append("")
        sections.append("[bold]Relations:[/bold]")
        for r in agg.relations:
            label = r.schema_term if r.schema_term == r.key else f"{r.key} (label: {r.schema_term})"
            props = ", ".join(f"{k}:{v}" for k, v in r.properties.items()) or "(none)"
            sources = ", ".join(r.sources)
            # Escape `[` so Rich doesn't interpret `[label]` as a style tag.
            sections.append(f"  {r.source_entity_key} --\\[{label}]--> {r.target_entity_key}")
            sections.append(f"    properties: {props}")
            sections.append(f"    [dim]from: {sources}[/dim]")
    console.print(Panel("\n".join(sections), title="KG schema", border_style="cyan", expand=False))


def _render_slot_resolution_rich(agg: MultiMappingPreview, all_files: list[str]) -> None:
    """Show which mapping file resolves each slot; flag unresolved slots."""
    all_slots = sorted(set(agg.slot_resolution) | set(agg.slot_unresolved) | set(agg.slot_deferred))
    if not all_slots:
        return
    lines: list[str] = []
    for slot in all_slots:
        resolvers = agg.slot_resolution.get(slot, [])
        unresolved_in = agg.slot_unresolved.get(slot, [])
        if resolvers:
            marker = "✓"
            color = "green"
            tail = ", ".join(resolvers)
            if len(resolvers) > 1:
                marker = "⚠"
                color = "yellow"
                tail = f"{tail} (resolved by multiple — should be a single source of truth)"
            lines.append(f"[{color}]{marker}[/{color}] {slot}   ← {tail}")
        elif unresolved_in:
            lines.append(f"[red]○[/red] {slot}   [dim](stub present in: {', '.join(unresolved_in)})[/dim]")
        if slot in agg.slot_deferred:
            lines.append(f"[yellow]—[/yellow] {slot}   deferred in: {', '.join(agg.slot_deferred[slot])} (known gap)")
    has_unresolved = bool(agg.slot_unresolved)
    border = "yellow" if has_unresolved else "green"
    console.print(Panel("\n".join(lines), title="Slot resolution", border_style=border, expand=False))


def _render_global_findings_rich(agg: MultiMappingPreview) -> None:
    """Project-level findings (cross-file conflicts, double-resolution)."""
    if not agg.findings:
        return
    lines = [f"[{f.severity}] {f.path}: {f.message}" for f in agg.findings]
    border = "red" if any(f.severity == "error" for f in agg.findings) else "yellow"
    console.print(
        Panel(
            "\n".join(lines),
            title="Project-level findings",
            border_style=border,
            expand=False,
        )
    )


def _render_per_file_panels(path: Path, result) -> None:
    """Render file-local information: structural validation findings."""
    has_findings = bool(result.findings)
    if not has_findings:
        return
    console.print(Panel(f"[bold]{path.name}[/bold]", border_style="cyan", expand=False))
    if has_findings:
        lines = [f"[{f.severity}] {f.path}: {f.message}" for f in result.findings]
        console.print(
            Panel(
                "\n".join(lines),
                title="Validation findings",
                border_style="red" if any(f.severity == "error" for f in result.findings) else "yellow",
                expand=False,
            )
        )


__all__ = ["map_group"]
