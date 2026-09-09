"""Research intent and payload-free Croissant inspection."""

from __future__ import annotations

import json
from pathlib import Path

import click
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from biotope.croissant.inspector import inspect_dataset, render_inspection
from biotope.croissant.spec import CroissantDatasetModel, load_from_path, load_from_url
from biotope.project_model import Project, find_project
from biotope.utils import find_biotope_root


console = Console()


@click.group(invoke_without_command=True, name="map")
@click.option("--purpose", "-p", type=str, default=None, help="Replace the project's purpose statement.")
@click.option("--entity", "-e", "entities", multiple=True, help="Add to required_entities. Repeatable.")
@click.option("--relation", "-r", "relations", multiple=True, help="Add to required_relations. Repeatable.")
@click.option("--source", "-s", "sources", multiple=True, help="Add to data_sources. Repeatable.")
@click.option("--notes", type=str, default=None, help="Replace the notes field.")
@click.option("--clear-entities", is_flag=True, help="Empty required_entities before adding.")
@click.option("--clear-relations", is_flag=True, help="Empty required_relations before adding.")
@click.option("--clear-sources", is_flag=True, help="Empty data_sources before adding.")
@click.option("--show", is_flag=True, help="Print project intent and exit.")
@click.pass_context
def map_group(
    ctx: click.Context,
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
    """Capture research intent and inspect Croissant metadata."""
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

    click.echo(ctx.get_help())
    click.echo(
        "\nDescribe data with biotope add; inspect metadata here. "
        "Generate typed sources with biotope source generate, then author Python mappings and use biotope graph check."
    )


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
    """Show declared sources and fields without reading source data."""
    dataset = _load_croissant(croissant)
    inspection = inspect_dataset(
        dataset,
    )
    if as_json:
        click.echo(json.dumps(inspection.to_json(), indent=2, default=str))
        return
    render_inspection(inspection, console)


def _load_croissant(path: str) -> CroissantDatasetModel:
    """Load a Croissant JSON-LD file with a friendly error for common mistakes.

    Accepts three input shapes:

    * a Croissant JSON-LD path or URL (canonical form),
    * a `.biotope.yaml` annotate scaffold path (suggests the right file),
    * a *data directory* that was previously ingested via ``biotope add`` —
      resolved to the canonical ``.biotope/datasets/<rel>.jsonld`` automatically.
    """
    # Keep stdout usable as JSON even when metadata cannot be loaded.
    console = Console(stderr=True)
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
                    f"Try:  [bold]biotope map inspect {suggestion}[/bold]"
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
    project_root = find_biotope_root()
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


def _suggest_croissant_jsonld(annotate_scaffold: Path) -> str | None:
    """Given a `.biotope.yaml` scaffold path, guess where its Croissant JSON-LD lives.

    `biotope add` writes the per-directory Croissant JSON-LD at
    ``.biotope/datasets/<same-relative-path>.jsonld`` — *a file named after the
    directory*, not a directory containing per-file jsonlds. We try that
    canonical form first, then fall back to a broader glob.
    """
    project_root = find_biotope_root()
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
