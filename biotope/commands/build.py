"""``biotope build`` — materialise a runnable BioCypher project from mappings.

Reads every ``mappings/*.mapping.yaml`` in the project, optionally an
``alignment.yaml`` at the project root, and emits a ``build/`` directory
containing ``config/schema_config.yaml``, the materialised mappings, per-mapping
generated Python under ``build/generated/<stem>/``, and a ``create_knowledge_graph.py``
entry point.

Strict: unresolved or legacy ``nodes``/``edges`` mappings cause the build to
abort with a regeneration hint.

**Headless ontology by default.** The generated ``biocypher_config.yaml`` sets
``head_ontology: null``, so the per-build class hierarchy is defined exclusively
by ``schema_config.yaml`` (regenerated deterministically from the resolved
mappings on every run). This avoids the remote Biolink fetch that has historically
made graph builds slow and fragile. Schema evolution happens *between* builds,
via ``project.yaml`` (``required_entities`` / ``required_relations``) and
``biotope map`` — never within a single build, so agents cannot reassign node
classes once the schema is locked in. To re-enable the Biolink hierarchy for a
specific project, edit the generated ``build/config/biocypher_config.yaml``
(biotope's "only write if missing" guard preserves user-authored configs).
"""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click
from rich.console import Console

from biotope.croissant.api import materialize
from biotope.project_model import Project, find_project


console = Console()

# `head_ontology: null` (biotope's headless-by-default config) requires
# BioCypher's NullOntology shim. Older versions silently ignore the key and
# fetch Biolink instead, which fails offline with a confusing network error.
MIN_BIOCYPHER_VERSION = (0, 15, 0)


def _check_biocypher_version() -> None:
    try:
        installed = version("biocypher")
    except PackageNotFoundError:
        return  # not installed in this env; nothing to assert against here
    parts = tuple(int(p) for p in installed.split(".")[:3] if p.isdigit())
    if parts < MIN_BIOCYPHER_VERSION:
        floor = ".".join(str(p) for p in MIN_BIOCYPHER_VERSION)
        click.echo(
            f"❌ Installed biocypher {installed} is older than {floor}, required for "
            "biotope's headless `head_ontology: null` config (older versions silently "
            "fetch Biolink instead, which fails offline). Upgrade biocypher first."
        )
        raise click.Abort


@click.command()
@click.option(
    "--mappings-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Directory of mapping YAML files. Default: <project_root>/mappings.",
)
@click.option(
    "--alignment",
    "alignment_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to alignment.yaml. Default: <project_root>/alignment.yaml if present.",
)
@click.option(
    "--out",
    "-o",
    "out_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to materialise the BioCypher project. Default: <project_root>/build.",
)
@click.option(
    "--target",
    type=click.Choice(["csv", "neo4j"]),
    default="csv",
    help="Output backend (`dbms:`) for a freshly-generated biocypher_config.yaml.",
)
def build(mappings_dir: Path | None, alignment_path: Path | None, out_dir: Path | None, target: str) -> None:
    """Build a deterministic BioCypher project from this biotope's mappings."""
    _check_biocypher_version()
    project_path = find_project()
    if project_path is None:
        click.echo("❌ No project.yaml found. Run `biotope init <name>` first.")
        raise click.Abort
    project_root = project_path.parent.parent if project_path.parent.name == ".biotope" else project_path.parent

    mappings_dir = mappings_dir or (project_root / "mappings")
    mapping_paths = _discover_mapping_paths(mappings_dir)

    if not mapping_paths:
        click.echo(f"❌ No mapping YAML files found under {mappings_dir}.")
        click.echo("   Run `biotope map scaffold <croissant>` first.")
        raise click.Abort

    if alignment_path is None:
        candidate = project_root / "alignment.yaml"
        if candidate.is_file():
            alignment_path = candidate

    project = Project.load(project_path)
    out_dir = out_dir or (project_root / "build")
    try:
        result = materialize(
            out_dir,
            mapping_paths,
            alignment_path,
            required_entities=list(project.required_entities),
            required_relations=list(project.required_relations),
            target=target,
        )
    except ValueError as exc:
        click.echo(f"❌ Build aborted: {exc}")
        raise click.Abort from exc

    console.print(f"✅ Built BioCypher project at [cyan]{out_dir}[/cyan]")
    console.print(f"   target (dbms): [bold]{result.get('dbms', target)}[/bold]")
    click.echo(json.dumps(result, indent=2, default=str))


def _discover_mapping_paths(mappings_dir: Path) -> list[Path]:
    """Return mapping YAML paths, preferring `*.mapping.yaml` over `*.yaml` duplicates."""
    candidates = sorted(mappings_dir.glob("*.yaml")) + sorted(mappings_dir.glob("*.yml"))
    selected: dict[str, Path] = {}

    for path in candidates:
        key = _mapping_identity(path)
        existing = selected.get(key)
        if existing is None or _mapping_path_rank(path) > _mapping_path_rank(existing):
            selected[key] = path

    return list(selected.values())


def _mapping_identity(path: Path) -> str:
    name = path.name
    for suffix in (".mapping.yaml", ".mapping.yml", ".yaml", ".yml"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _mapping_path_rank(path: Path) -> int:
    name = path.name
    if name.endswith((".mapping.yaml", ".mapping.yml")):
        return 2
    if name.endswith((".yaml", ".yml")):
        return 1
    return 0
