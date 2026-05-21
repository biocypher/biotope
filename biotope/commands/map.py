"""``biotope map`` — semantic mapping authoring commands.

* ``biotope map`` (bare) launches the guided wizard, unless any intent flag
  (``--purpose``, ``--entity``, ``--relation``, ``--source``, ``--notes``,
  ``--clear-*``, ``--show``) is present, in which case it applies the edit
  non-interactively and exits.
* ``biotope map inspect <croissant>`` — deterministic Croissant/data inspector.
* ``biotope map scaffold <croissant>`` — non-interactive unresolved scaffold.
* ``biotope map preview [<mapping>]`` — compile-in-memory preview.

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

from biotope.croissant.api import scaffold_mapping
from biotope.croissant.mapping import (
    Mapping,
    inspect_dataset,
    load_mapping,
    preview_mapping,
    render_inspection_text,
)
from biotope.croissant.spec import CroissantDatasetModel, load_from_path, load_from_url
from biotope.project_model import Project, find_project, resolve_project_path

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
@click.option("--preview-rows", type=click.IntRange(min=0), default=3, show_default=True)
def inspect(croissant: str, as_json: bool, preview_rows: int) -> None:
    """Inspect a Croissant dataset deterministically."""
    dataset = _load_croissant(croissant)
    datasets_location = _infer_datasets_location(croissant)
    inspection = inspect_dataset(
        dataset,
        datasets_location=datasets_location,
        preview_rows=preview_rows,
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
@click.option("--preview-rows", type=click.IntRange(min=0), default=3, show_default=True)
def scaffold(croissant: str, out: Path | None, to_stdout: bool, preview_rows: int) -> None:
    """Generate an unresolved semantic mapping scaffold for a Croissant file."""
    if out is not None and to_stdout:
        raise click.UsageError("Choose either --out or --stdout, not both.")

    _load_croissant(croissant)  # validate up front with friendly errors

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
        preview_rows=preview_rows,
    )
    if target:
        console.print(f"✅ Wrote {target}")
        unresolved = result.get("unresolved") or []
        if unresolved:
            console.print(
                f"[yellow]ℹ[/yellow] {len(unresolved)} unresolved slot(s); "
                f"run [bold]biotope map[/bold] to resolve."
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
@click.option("--rows", "sample_rows", type=click.IntRange(min=0), default=3, show_default=True)
def preview(mapping_path: Path | None, as_json: bool, sample_rows: int) -> None:
    """Validate a (partial) mapping and project its outputs."""
    if mapping_path is None:
        mapping_path = _discover_single_mapping()
        if mapping_path is None:
            click.echo("❌ No mapping file found. Pass a path or run `biotope map scaffold` first.")
            raise click.Abort
    mapping = load_mapping(mapping_path)
    dataset = _load_croissant(mapping.croissant)
    datasets_location = _infer_datasets_location(mapping.croissant)
    result = preview_mapping(
        mapping,
        dataset,
        datasets_location=datasets_location,
        sample_rows=sample_rows,
    )
    if as_json:
        click.echo(json.dumps(result.to_json(), indent=2, default=str))
        return
    _render_preview_rich(mapping, result)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


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
            console.print(
                f"❌ Could not load Croissant file from URL: [cyan]{path}[/cyan]\n   {exc}"
            )
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
                f"This is a [yellow]biotope annotate scaffold[/yellow], not a Croissant JSON-LD file.\n"
                f"`biotope map` expects the Croissant metadata for a dataset, which lives under "
                f"[cyan].biotope/datasets/[/cyan].\n\n"
                + (f"Try:  [bold]biotope map -c {suggestion}[/bold]" if suggestion else
                   "Run [bold]biotope add <data>[/bold] first to generate the Croissant file under "
                   "[cyan].biotope/datasets/[/cyan]."),
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
    nested = sorted((datasets_root / rel).rglob("*.jsonld")) + sorted(
        (datasets_root / rel).rglob("*.croissant.json")
    )
    return nested[0] if nested else None


def discover_croissants(project_root: Path) -> list[Path]:
    """Return all Croissant metadata files under a project's ``.biotope/datasets/``.

    Looks for both ``*.jsonld`` (baker output) and ``*.croissant.json`` (legacy /
    user-supplied) shapes.
    """
    datasets_root = project_root / ".biotope" / "datasets"
    if not datasets_root.is_dir():
        return []
    files = sorted(datasets_root.rglob("*.jsonld")) + sorted(
        datasets_root.rglob("*.croissant.json")
    )
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
        candidates = sorted(datasets_root.rglob("*.jsonld")) + sorted(
            datasets_root.rglob("*.croissant.json")
        )
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


def _infer_datasets_location(croissant_path: str | Path) -> Path | None:
    """Locate the on-disk data root for a Croissant file.

    Baker writes per-directory Croissants at
    ``<project>/.biotope/datasets/<rel>.jsonld``, with ``includes`` paths
    relative to the original data directory at ``<project>/<rel>/``.
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
            return data_dir if data_dir.exists() else biotope_root
    return path.parent


def _render_preview_rich(mapping: Mapping, result) -> None:
    if result.resolved_slots:
        console.print(
            Panel(
                "\n".join(f"✓ {s}" for s in result.resolved_slots),
                title="Resolved slots",
                border_style="green",
                expand=False,
            )
        )
    if result.unresolved_slots:
        console.print(
            Panel(
                "\n".join(f"○ {s}" for s in result.unresolved_slots),
                title="Unresolved slots",
                border_style="yellow",
                expand=False,
            )
        )
    if result.findings:
        lines = [f"[{f.severity}] {f.path}: {f.message}" for f in result.findings]
        console.print(
            Panel(
                "\n".join(lines),
                title="Validation findings",
                border_style="red" if any(f.severity == "error" for f in result.findings) else "yellow",
                expand=False,
            )
        )
    if result.entities or result.relations:
        sections: list[str] = ["[bold]Entities:[/bold]"]
        for e in result.entities:
            props = ", ".join(f"{k}:{v}" for k, v in e.properties.items()) or "(none)"
            sections.append(
                f"  {e.key} -> {e.schema_term} [namespace={e.namespace}, input_label={e.input_label}]\n"
                f"    properties: {props}"
            )
        sections.append("[bold]Relations:[/bold]")
        for r in result.relations:
            props = ", ".join(f"{k}:{v}" for k, v in r.properties.items()) or "(none)"
            sections.append(
                f"  {r.key} -> {r.schema_term} [{r.source} -> {r.target}, input_label={r.input_label}]\n"
                f"    properties: {props}"
            )
        console.print(
            Panel(
                "\n".join(sections), title="Projected schema", border_style="cyan", expand=False
            )
        )
    if result.sample_node_tuples or result.sample_edge_tuples:
        lines = []
        if result.sample_node_tuples:
            lines.append("[bold]Sample node tuples:[/bold]")
            for tup in result.sample_node_tuples:
                lines.append(f"  ({tup[0]!r}, {tup[1]!r}, {tup[2]!r})")
        if result.sample_edge_tuples:
            lines.append("[bold]Sample edge tuples (rel_id, source, target, label, props):[/bold]")
            for tup in result.sample_edge_tuples:
                lines.append(
                    f"  ({tup[0]!r}, {tup[1]!r}, {tup[2]!r}, {tup[3]!r}, {tup[4]!r})"
                )
        console.print(Panel("\n".join(lines), title="Samples", border_style="dim", expand=False))


__all__ = ["map_group"]
