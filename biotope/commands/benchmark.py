"""``biotope benchmark`` — quality and coverage metrics for a built graph.

v1 promise: emit a JSON skeleton with structured slots for metrics so
downstream tooling can already structure-test against it. Real metric
implementations land iteratively.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console

from biotope.project_model import find_project

console = Console()


@click.command()
@click.option(
    "--build-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Path to a build/ directory. Default: <project_root>/build.",
)
@click.option("--out", "-o", type=click.Path(dir_okay=False, path_type=Path), default=None)
def benchmark(build_dir: Path | None, out: Path | None) -> None:
    """Emit quality/coverage metrics for a built graph as JSON.

    v1 stub: skeleton metrics object so downstream consumers can assert shape.
    Real implementations will populate ``coverage``, ``id_consistency``, and
    ``alignment_yield`` over time.
    """
    if build_dir is None:
        project_path = find_project()
        if project_path is None:
            click.echo("❌ No project.yaml found. Pass --build-dir or run `biotope init` first.")
            raise click.Abort
        project_root = (
            project_path.parent.parent if project_path.parent.name == ".biotope" else project_path.parent
        )
        build_dir = project_root / "build"

    report = {
        "build_dir": str(build_dir),
        "metrics": {
            "coverage": {
                "implemented": False,
                "description": "Fraction of required_entities present in build output.",
            },
            "id_consistency": {
                "implemented": False,
                "description": "Fraction of edge endpoints resolving to existing nodes.",
            },
            "alignment_yield": {
                "implemented": False,
                "description": "Number of cross-Croissant ID collapses produced.",
            },
        },
    }
    payload = json.dumps(report, indent=2)
    if out:
        Path(out).write_text(payload + "\n")
        console.print(f"✅ Wrote {out}")
    else:
        click.echo(payload)
