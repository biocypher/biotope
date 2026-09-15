"""Derived topology documents and offline rendering, without pipeline execution."""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import fields
from importlib.resources import files
from typing import Any

from biotope.graph.artifacts import HTML_MARKER
from biotope.graph.sources import digest
from biotope.graph.topology import Topology, concept_id


def _label(cls: type) -> str:
    authored = getattr(cls, "display_name", None)
    if isinstance(authored, str) and authored.strip():
        return authored.strip()
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", cls.__name__)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ")


def describe_metagraph(topology: Topology, report: dict[str, Any] | None = None) -> dict[str, Any]:
    """Describe declarations and optionally overlay measurements from a matching run."""
    schema = topology.describe()
    revision = digest(schema)
    measurements: dict[str, Any] = {}
    findings: list[dict[str, Any]] = []
    run: dict[str, Any] | None = None
    mappings: dict[str, Any] = {}
    if report is not None:
        definitions: dict[str, Any] = report.get("definitions") or {}
        if definitions.get("topology_digest") != revision:
            raise ValueError("Report topology does not match the selected Python topology; select a matching report")
        quality: dict[str, Any] = report.get("quality") or {}
        measured = quality.get("state") == "complete" and "measurements" in quality
        if measured:
            measurements = quality["measurements"]
            findings = quality.get("findings", [])
        run = {k: report.get(k) for k in ("operation", "state", "scope", "pipeline", "started", "finished", "error")}
        run["quality_state"] = (
            quality.get("state", "unmeasured") if measured or quality.get("state") == "not_run" else "unmeasured"
        )
        mappings = definitions.get("mappings", {})
    result: dict[str, Any] = {
        "schema_version": 1,
        "report_kind": "biotope.metagraph",
        "state": "complete",
        "topology_digest": revision,
        "nodes": [],
        "edges": [],
        "report": run,
        "measurements": measurements,
        "findings": findings,
    }
    for cls in (*topology.nodes, *topology.edges):
        concept = concept_id(cls)
        item = schema[concept]
        description = cls.__dict__.get("__doc__") or ""
        # Dataclasses synthesize a signature docstring; it is not an authored description.
        if description.startswith(cls.__name__ + "("):
            description = ""
        source = inspect.getsourcefile(cls)
        try:
            line = inspect.getsourcelines(cls)[1]
        except (OSError, TypeError):
            line = None
        members = {f.name: f for f in fields(cls)}
        component: dict[str, Any] = {
            "id": concept,
            "kind": item["kind"],
            "name": cls.__name__,
            "label": _label(cls),
            "declaration": {"module": cls.__module__, "class": cls.__qualname__, "path": source, "line": line},
            "description": inspect.cleandoc(description),
            "source": item["source"],
            "target": item["target"],
            "count": measurements.get("population", {}).get(concept),
            "mappings": [name for name, mapping in mappings.items() if concept in mapping.get("concepts", [])],
            "observations": {
                name: value[concept]
                for name, value in measurements.items()
                if name not in ("population", "properties") and isinstance(value, dict) and concept in value
            },
            "properties": [
                {
                    "name": name,
                    "type": kind,
                    "nullable": name in item["nullable"],
                    "description": members[name].metadata.get("description"),
                    "statistics": measurements.get("properties", {}).get(concept, {}).get(name),
                }
                for name, kind in item["properties"].items()
            ],
            "findings": [f for f in findings if f["subject"] == concept or f["subject"].startswith(concept + ".")],
        }
        result["nodes" if item["kind"] == "node" else "edges"].append(component)
    return result


def render_metagraph(document: dict[str, Any]) -> str:
    """Embed data and pinned assets into one safe, standalone HTML artifact."""
    assets = files("biotope.graph").joinpath("static")
    template = assets.joinpath("metagraph.html").read_text(encoding="utf-8")
    payload = (
        json.dumps(document, ensure_ascii=True, allow_nan=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    # Inject data last so a marker-like value cannot cause a second substitution.
    return (
        HTML_MARKER
        + "\n"
        + template.replace("%%D3%%", assets.joinpath("d3.v7.min.js").read_text(encoding="utf-8")).replace(
            "%%DATA%%", payload
        )
    )
