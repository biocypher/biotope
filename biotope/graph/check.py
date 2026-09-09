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
from typing import Any, cast, get_args, get_type_hints

from biotope.graph.contracts import Pipeline
from biotope.graph.reports import (
    CheckFailed,
    CheckResult,
    DefinitionReport,
    Finding,
    FindingSink,
    Location,
    Phase,
    PythonCheckFailed,
)
from biotope.graph.sources import UnknownValue, check_generated, contract_digests, digest, read_metadata
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


def check_types(pipeline: Pipeline, *, on_finding: FindingSink | None = None) -> dict[str, object]:
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
    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        raise ValueError(
            "Could not run Pyright; check python -m pyright --version.\n" + (result.stderr or result.stdout)
        ) from exc
    findings = [
        Finding(
            "python." + item.get("rule", "diagnostic"),
            item.get("severity", "error"),
            item.get("file", "Python"),
            item["message"],
            Location(
                item["file"],
                item.get("range", {}).get("start", {}).get("line", 0) + 1,
                item.get("range", {}).get("start", {}).get("character", 0) + 1,
            ),
        )
        for item in payload.get("generalDiagnostics", [])
    ]
    if result.returncode:
        raise PythonCheckFailed(
            findings or [Finding("python.execution", "error", "Python", result.stderr or "Pyright failed")]
        )
    summary = json.loads(result.stdout)["summary"]
    if summary["filesAnalyzed"] < len(files):
        raise ValueError("Pyright did not analyze all registered Python files; inspect code_paths and checker output")
    if on_finding:
        for finding in findings:
            on_finding(finding)
    return summary


def _contains_unknown(annotation: object) -> bool:
    return annotation is UnknownValue or any(_contains_unknown(arg) for arg in get_args(annotation))


def check_pipeline(
    pipeline: Pipeline, *, static: bool = True, phase: Phase | None = None, on_finding: FindingSink | None = None
) -> dict[str, Any]:
    """Collect independent definition failures; never invoke project data functions."""
    report = DefinitionReport(
        data={
            "pipeline": pipeline.name,
            "scope": "definitions only",
            "selected_scope": pipeline.scope,
            "topology": None,
            "topology_digest": None,
            "sources": {},
            "mappings": {},
            "intent": None,
            "requirements": pipeline.requirements,
            "deferrals": pipeline.deferrals,
            "code_digests": {},
        }
    )

    def add_finding(finding: Finding) -> None:
        report.findings.append(finding)
        if on_finding:
            on_finding(finding)

    def stage(name: str, action: Any, *, blocked: str = "") -> Any:
        if blocked:
            report.checks.append(CheckResult(name, "skipped", blocked))
            return None
        if phase:
            phase(name)
        start = len(report.findings)
        value = None
        try:
            value = action()
        except PythonCheckFailed as exc:
            for finding in exc.findings:
                add_finding(finding)
        except Exception as exc:
            add_finding(Finding(name + ".invalid", "error", name, str(exc)))
        failed = any(f.severity == "error" for f in report.findings[start:])
        report.checks.append(CheckResult(name, "failed" if failed else "passed"))
        return value

    def error(code: str, subject: str, message: str, path: Path | None = None) -> None:
        add_finding(Finding(code, "error", subject, message, Location(str(path)) if path else None))

    def warning(code: str, subject: str, message: str) -> None:
        add_finding(Finding(code, "warning", subject, message))

    def identity() -> None:
        if not pipeline.name.strip() or not pipeline.scope.strip():
            raise ValueError("Pipeline needs a stable name and explicit selected scope")

    stage("pipeline", identity)
    schema = stage("topology", pipeline.topology.describe)
    if schema is not None:
        report.data.update(topology=schema, topology_digest=digest(schema))
        examples = [key for key in schema if key.startswith("example:")]
        if examples:
            warning(
                "topology.examples",
                "topology",
                "Registered example: concepts are illustrative placeholders: " + ", ".join(examples),
            )

    def paths() -> tuple[Path, ...] | None:
        try:
            return code_files(pipeline)
        except ValueError as exc:
            error("code.paths", "code_paths", str(exc))
            return None

    files: tuple[Path, ...] | None = stage("code", paths)

    def revisions() -> dict[str, str]:
        assert files is not None
        return {str(p): digest(p.read_text(encoding="utf-8")) for p in files}

    report.data["code_digests"] = (
        stage("revisions", revisions, blocked="Code paths are invalid" if files is None else "") or {}
    )

    declared: set[Path] = set(files or ())

    def sources() -> None:
        seen: set[str] = set()
        for source in pipeline.sources:
            try:
                if source.name in seen:
                    raise ValueError(f"Duplicate source registration {source.name}")
                seen.add(source.name)
                check_generated(source.metadata, source.generated)
                if files is not None and source.generated.resolve() not in declared:
                    raise ValueError(f"{source.generated}: include generated source contracts in code_paths")
                metadata = read_metadata(source.metadata)
                revisions = contract_digests(metadata)
                covered: list[str] = []
                for record in source.records:
                    identity = getattr(record, "__record_set__", None)
                    # A record set removed from the manifest has no digest to match.
                    expected = revisions.get(identity) if isinstance(identity, str) else None
                    if (
                        not is_dataclass(record)
                        or expected is None
                        or getattr(record, "__source_digest__", None) != expected
                    ):
                        raise ValueError(
                            f"{source.name}: stale or non-generated record {record}; regenerate and restart the process"
                        )
                    covered.append(cast(str, identity))
                    if Path(inspect.getfile(record)).resolve() != source.generated.resolve():
                        raise ValueError(f"{record}: record does not come from the registered generated module")
                    for member in fields(record):
                        if _contains_unknown(get_type_hints(record)[member.name]):
                            warning(
                                "source.opaque",
                                f"{source.name}.{record.__name__}.{member.name}",
                                "opaque source contract; refine metadata before using values",
                            )
                report.data["sources"][source.name] = {
                    "metadata": str(source.metadata),
                    "digest": digest(metadata),
                    "contract_digest": digest(sorted(revisions[identity] for identity in covered)),
                    "distribution": metadata.get("distribution", []),
                    "records": [getattr(r, "__record_set__") for r in source.records],
                }
            except Exception as exc:
                error("source.contract", source.name, str(exc), source.metadata)

    stage("sources", sources)

    def mappings() -> None:
        seen: set[str] = set()
        for mapping in pipeline.mappings:
            try:
                if not mapping.name.strip() or mapping.name in seen:
                    raise ValueError(f"Empty or duplicate mapping identity {mapping.name!r}")
                seen.add(mapping.name)
                params = list(inspect.signature(mapping.function).parameters.values())
                annotations = get_type_hints(mapping.function)
                if len(params) != len(mapping.inputs) or any(
                    annotations.get(p.name) is not expected for p, expected in zip(params, mapping.inputs)
                ):
                    raise ValueError("Function annotations must match registered input contracts")
                if "return" not in annotations or not mapping.outputs:
                    raise ValueError("Annotate the iterable return type and declare output contracts")
                report.data["mappings"][mapping.name] = {
                    "inputs": [t.__name__ for t in mapping.inputs],
                    "outputs": [t.__name__ for t in mapping.outputs],
                    "concepts": [
                        getattr(t, "schema_id")
                        for t in mapping.outputs
                        if t in (*pipeline.topology.nodes, *pipeline.topology.edges)
                    ],
                    "requirements": mapping.requirements,
                    "evidence": mapping.evidence,
                }
            except Exception as exc:
                error("mapping.contract", mapping.name, str(exc))

    stage("mappings", mappings)

    def declarations() -> None:
        for item in (
            *pipeline.topology.nodes,
            *pipeline.topology.edges,
            pipeline.run,
            *(m.function for m in pipeline.mappings),
        ):
            try:
                path = Path(inspect.getfile(item)).resolve()
                if path not in declared:
                    error("code.declaration", str(item), "Include its authored module in code_paths", path)
            except (TypeError, OSError) as exc:
                error("code.declaration", str(item), str(exc))

    stage("declarations", declarations, blocked="Code paths are invalid" if files is None else "")

    def intent() -> Any:
        path = pipeline.intent or find_project()
        if path is None:
            warning(
                "intent.absent",
                "intent",
                "No intent found; research purpose and requirement coverage were not checked.",
            )
            return {}
        value = Project.load(path)
        report.data["intent"] = value.model_dump()
        if not value.purpose.strip():
            warning(
                "intent.purpose",
                "intent",
                "No research purpose stated in the intent; scientific relevance is unresolved.",
            )
        if not value.required_entities and not value.required_relations:
            warning(
                "intent.requirements",
                "intent",
                "No required entities or relations declared; requirement coverage is unspecified.",
            )
        return {
            **{f"entity:{n}": "node" for n in value.required_entities},
            **{f"relation:{n}": "edge" for n in value.required_relations},
        }

    required = stage("intent", intent)

    def requirements() -> None:
        assert schema is not None and required is not None
        for key, reason in pipeline.deferrals.items():
            if not reason.strip() or key in pipeline.requirements:
                error("requirements.invalid", key, "A deferral needs a reason and cannot also be resolved")
        for key, semantic in pipeline.requirements.items():
            if semantic not in schema or (key in required and schema[semantic]["kind"] != required[key]):
                error("requirements.invalid", key, f"Requirement points to missing/wrong topology concept {semantic}")
        for key in sorted(set(required) - set(pipeline.requirements) - set(pipeline.deferrals)):
            error("requirements.unresolved", key, "Bind this purpose requirement or explicitly defer with a reason")
        for key in sorted((set(pipeline.requirements) | set(pipeline.deferrals)) - set(required)):
            warning("requirements.unknown", key, f"{key}: reference is not in the current intent lists")

    stage(
        "requirements",
        requirements,
        blocked="Topology or intent is invalid" if schema is None or required is None else "",
    )
    if static:
        summary = stage(
            "python",
            lambda: check_types(pipeline, on_finding=add_finding),
            blocked="Code paths are invalid" if files is None else "",
        )
        if summary is not None:
            report.data["type_check"] = summary
    else:
        report.checks.append(CheckResult("python", "skipped", "Static checking disabled by the API caller"))
    result = report.to_json()
    if result["state"] == "failed":
        raise CheckFailed(result)
    return result
