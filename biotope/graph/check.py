"""Definition checks and the real static checker; no loader invocation."""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, get_args, get_type_hints

from biotope.graph.contracts import Pipeline
from biotope.graph.sources import UnknownValue, check_generated, digest, read_metadata, source_definition
from biotope.project_model import Project, find_project


def code_files(pipeline: Pipeline) -> tuple[Path, ...]:
    """Enumerate declared Python paths only, never source payload paths."""
    files: set[Path] = set()
    for declared in pipeline.code_paths:
        path = Path(declared).resolve()
        if path.is_dir():
            for directory, children, names in os.walk(path):
                children[:] = [name for name in children if name not in {"__pycache__", ".venv", "venv", ".git"}]
                files.update(Path(directory) / name for name in names if name.endswith(".py"))
        elif path.is_file() and path.suffix == ".py":
            files.add(path)
        else:
            raise ValueError(f"Code path {path} is missing or is not Python source")
    if not files:
        raise ValueError("Register the generated and authored Python in Pipeline.code_paths")
    return tuple(sorted(files))


def check_types(pipeline: Pipeline) -> dict[str, object]:
    """Run Pyright in strict mode over the declared project code."""
    if importlib.util.find_spec("pyright") is None:
        raise ValueError("Install biotope[graph] in this environment for Pyright and BioCypher")
    config = {
        "include": [],
        "exclude": [],
        "typeCheckingMode": "strict",
        "pythonVersion": f"{sys.version_info.major}.{sys.version_info.minor}",
        "extraPaths": [str(Path.cwd())],
        "reportMissingTypeStubs": "none",
    }
    files = code_files(pipeline)
    with tempfile.TemporaryDirectory(prefix="biotope-pyright-", dir=Path.cwd()) as temporary:
        path = Path(temporary) / "pyrightconfig.json"
        config["include"] = [os.path.relpath(item, path.parent) for item in files]
        path.write_text(json.dumps(config), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "pyright", "--project", str(path), "--pythonpath", sys.executable, "--outputjson"],
            text=True,
            capture_output=True,
            check=False,
        )
    if result.returncode:
        try:
            report = json.loads(result.stdout)
            diagnostics = "\n".join(
                f"{item['file']}:{item.get('range', {}).get('start', {}).get('line', 0) + 1}: {item['message']}"
                for item in report.get("generalDiagnostics", [])
            )
        except (ValueError, KeyError) as exc:
            raise ValueError(
                "Could not run Pyright. Check the graph extra and Node installation with "
                "python -m pyright --version.\n" + (result.stderr or result.stdout)
            ) from exc
        if "too complex" in diagnostics.lower():
            raise ValueError(
                "Pyright could not analyze this module's complexity. Regenerate source contracts with the current "
                "Biotope generator. If it persists, split the curated record sets into smaller source contracts.\n"
                + "\n".join(line for line in diagnostics.splitlines() if "too complex" in line.lower())
            )
        raise ValueError("Static checking failed:\n" + (diagnostics or result.stderr))
    summary = json.loads(result.stdout)["summary"]
    if summary["filesAnalyzed"] < len(files):
        raise ValueError("Pyright did not analyze all registered Python files; inspect code_paths and checker output")
    return summary


def _contains_unknown(annotation: object) -> bool:
    return annotation is UnknownValue or any(_contains_unknown(arg) for arg in get_args(annotation))


def check_pipeline(pipeline: Pipeline, *, static: bool = True) -> dict[str, Any]:
    """Check source freshness, semantic contracts, purpose coverage and Python types."""
    if not pipeline.name.strip() or not pipeline.scope.strip():
        raise ValueError("Pipeline needs a stable name and explicit selected scope")
    schema = pipeline.topology.describe()
    files = code_files(pipeline)
    declared_files = set(files)
    sources: dict[str, object] = {}
    warnings: list[str] = []
    for source in pipeline.sources:
        if source.name in sources:
            raise ValueError(f"Duplicate source registration {source.name}")
        check_generated(source.metadata, source.generated)
        if source.generated.resolve() not in declared_files:
            raise ValueError(f"{source.generated}: include generated source contracts in code_paths")
        metadata = read_metadata(source.metadata)
        revision = digest(source_definition(metadata))
        for record in source.records:
            if not is_dataclass(record) or getattr(record, "__source_digest__", None) != revision:
                raise ValueError(
                    f"{source.name}: stale or non-generated record {record}; regenerate and restart the process"
                )
            if Path(inspect.getfile(record)).resolve() != source.generated.resolve():
                raise ValueError(f"{record}: record does not come from the registered generated module")
            hints = get_type_hints(record)
            for member in fields(record):
                if _contains_unknown(hints[member.name]):
                    warnings.append(
                        f"{source.name}.{record.__name__}.{member.name}: opaque source contract; "
                        "refine metadata before using values"
                    )
        sources[source.name] = {
            "metadata": str(source.metadata),
            "digest": digest(metadata),
            "contract_digest": revision,
            "distribution": metadata.get("distribution", []),
            "records": [getattr(record, "__record_set__") for record in source.records],
        }
    mappings: dict[str, object] = {}
    for mapping in pipeline.mappings:
        if not mapping.name.strip() or mapping.name in mappings:
            raise ValueError(f"Empty or duplicate mapping identity {mapping.name!r}")
        parameters = list(inspect.signature(mapping.function).parameters.values())
        annotations = get_type_hints(mapping.function)
        if len(parameters) != len(mapping.inputs) or any(
            annotations.get(param.name) is not expected for param, expected in zip(parameters, mapping.inputs)
        ):
            raise ValueError(f"{mapping.name}: function annotations must match the registered input contracts")
        if "return" not in annotations:
            raise ValueError(f"{mapping.name}: annotate the mapping's iterable return type")
        if not mapping.outputs:
            raise ValueError(f"{mapping.name}: declare output contracts")
        mappings[mapping.name] = {
            "inputs": [t.__name__ for t in mapping.inputs],
            "outputs": [t.__name__ for t in mapping.outputs],
            "requirements": mapping.requirements,
            "evidence": mapping.evidence,
        }
    for declaration in (
        *pipeline.topology.nodes,
        *pipeline.topology.edges,
        pipeline.run,
        *(m.function for m in pipeline.mappings),
    ):
        if Path(inspect.getfile(declaration)).resolve() not in declared_files:
            raise ValueError(f"{declaration}: include its authored module in code_paths")
    required: dict[str, str] = {}
    intent_path = pipeline.intent or find_project()
    intent = Project.load(intent_path) if intent_path else None
    if intent is None:
        warnings.append("No intent found; research purpose and requirement coverage were not checked.")
    else:
        if not intent.purpose.strip():
            warnings.append("No research purpose stated in the intent; scientific relevance is unresolved.")
        if not intent.required_entities and not intent.required_relations:
            warnings.append("No required entities or relations declared; requirement coverage is unspecified.")
        required = {
            **{f"entity:{name}": "node" for name in intent.required_entities},
            **{f"relation:{name}": "edge" for name in intent.required_relations},
        }
    examples = [concept for concept in schema if concept.startswith("example:")]
    if examples:
        warnings.append(
            "Registered example: concepts are illustrative placeholders; review before research use: "
            + ", ".join(examples)
        )
    for key, reason in pipeline.deferrals.items():
        if not reason.strip() or key in pipeline.requirements:
            raise ValueError(f"{key}: a deferral needs a reason and cannot also be resolved")
    for key, semantic in pipeline.requirements.items():
        if semantic not in schema or (key in required and schema[semantic]["kind"] != required[key]):
            raise ValueError(f"{key}: requirement points to missing/wrong topology concept {semantic}")
    missing = set(required) - set(pipeline.requirements) - set(pipeline.deferrals)
    if missing:
        raise ValueError(
            f"Unresolved purpose requirements: {sorted(missing)}; bind them or explicitly defer with reasons"
        )
    for key in (set(pipeline.requirements) | set(pipeline.deferrals)) - set(required):
        warnings.append(f"{key}: reference is not in the current intent lists")
    result: dict[str, Any] = {
        "state": "checked",
        "scope": "definitions only; no source values or scientific validity checked",
        "pipeline": pipeline.name,
        "selected_scope": pipeline.scope,
        "topology": schema,
        "topology_digest": digest(schema),
        "sources": sources,
        "mappings": mappings,
        "intent": intent.model_dump() if intent else None,
        "requirements": pipeline.requirements,
        "deferrals": pipeline.deferrals,
        "warnings": warnings,
        "code_digests": {str(path): digest(path.read_text(encoding="utf-8")) for path in files},
    }
    if static:
        result["type_check"] = check_types(pipeline)
    return result
