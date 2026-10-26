from pathlib import Path

import click

from biotope.graph.revisions import short_revision
from biotope.graph.survey import survey_sources
from biotope.utils import find_biotope_root


@click.command(
    help="List the dataset manifests in .biotope/datasets and mark those whose revision differs from the one "
    "their source package in graph/sources pins."
)
def status() -> None:
    root = find_biotope_root()
    if root is None:
        raise click.ClickException("Not in a biotope project. Run 'biotope init' first.")
    datasets = root / ".biotope/datasets"
    sources = root / "graph/sources"
    plans = survey_sources(sources).plans if sources.is_dir() else ()
    drifts: dict[Path, list[str]] = {}
    for plan in plans:
        for item in plan.statuses:
            if item.state == "drift":
                drifts.setdefault(plan.metadata.resolve(), []).append(
                    f"{item.path.relative_to(root).as_posix()}: pinned {short_revision(item.acknowledged)}, "
                    f"now {short_revision(item.revision)}"
                )
    generated = {plan.metadata.resolve() for plan in plans}
    manifests = sorted(datasets.rglob("*.jsonld")) if datasets.is_dir() else []
    if not manifests:
        click.echo("No datasets. Describe data with biotope add <path>.")
    for manifest in manifests:
        name = manifest.relative_to(datasets).with_suffix("").as_posix()
        changed = drifts.get(manifest.resolve())
        label = "Changed" if changed else "Current" if manifest.resolve() in generated else "No source"
        click.echo(f"{label:<9} {name}")
        for line in changed or ():
            click.echo(f"{'':<9} {line}")
