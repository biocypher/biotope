"""The interpretation context that travels with an exported graph.

Biotope validates and transports this material. Every statement in it is the
project's own; nothing here invents biomedical semantics.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, timezone
from typing import Any

from biotope.graph.contracts import Pipeline
from biotope.graph.reports import Finding
from biotope.graph.sources import digest
from biotope.graph.topology import ConceptDescription, ConceptSchema


GUIDANCE = (
    "Project-authored interpretation rules for this graph. Resolve the study and comparison "
    "you mean, then read every interpretation attached to the concepts and properties your "
    "query touches before filtering, joining or comparing directions. A capability that is "
    "not 'supported' has not been shown to work; an absent statement is missing knowledge, "
    "not permission."
)

CONTEXT_CONCEPT = "biotope:query-context"
CONTEXT_LABEL = "BiotopeQueryContext"
CONTEXT_PROPERTIES = {"entry": "str", "subject": "str", "label": "str", "statement": "str", "detail": "str"}

ENCODING = (
    r"Text is escaped so a multi-line value survives one CSV cell: \n is a newline, "
    r"\r a carriage return, \t a tab and \\ a literal backslash. Reverse those four "
    "to recover the original, and preserve interior spacing exactly."
)
_ESCAPED = {"\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
_UNESCAPED = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\"}


def encode_text(value: str) -> str:
    """Escape a value so it survives one single-line cell without losing characters."""
    return "".join(_ESCAPED.get(char, char) for char in value)


def decode_text(value: str) -> str:
    """Reverse :func:`encode_text`."""
    out: list[str] = []
    chars = iter(value)
    for char in chars:
        if char != "\\":
            out.append(char)
            continue
        following = next(chars, "")
        out.append(_UNESCAPED.get(following, "\\" + following))
    return "".join(out)


def _reference(subject: str, concepts: Collection[str]) -> tuple[str, str]:
    """Resolve a reference to a concept and an optional property suffix.

    An exact concept match wins, so a concept ID containing periods stays
    addressable; otherwise the final period separates the property.
    """
    if subject in concepts:
        return subject, ""
    concept, _, prop = subject.rpartition(".")
    return (concept, prop) if concept else (subject, "")


def _described(descriptions: dict[str, ConceptDescription], concept: str) -> ConceptDescription:
    """Read authored meaning for one concept, treating an absent entry as undescribed."""
    found = descriptions.get(concept)
    return found if found is not None else {"description": "", "properties": {}}


def _resolve(subject: str, schema: dict[str, ConceptSchema]) -> str:
    """Return an empty string when a reference is valid, else why it is not."""
    concept, prop = _reference(subject, schema)
    if concept not in schema:
        return f"no topology concept {concept!r}"
    if prop and prop not in schema[concept]["properties"] and prop not in ("id", "source", "target"):
        return f"concept {concept} has no property {prop!r}"
    return ""


def check_query_context(
    pipeline: Pipeline, schema: dict[str, ConceptSchema], descriptions: dict[str, ConceptDescription]
) -> list[Finding]:
    """Check that every declared rule points at something the export will contain."""
    findings: list[Finding] = []
    context = pipeline.query_context

    def error(subject: str, message: str) -> None:
        findings.append(Finding("context.invalid", "error", subject, message))

    def warning(code: str, subject: str, message: str) -> None:
        findings.append(Finding(code, "warning", subject, message))

    for item in context.interpretations:
        problem = _resolve(item.subject, schema)
        if problem:
            error(item.subject, f"Interpretation points at {problem}")
        if not item.statement.strip():
            error(item.subject, "An interpretation needs a statement a reader can act on")
        for alternative in item.alternatives:
            problem = _resolve(alternative, schema)
            if problem:
                error(
                    item.subject,
                    f"Alternative {alternative!r} points at {problem}. An alternative names another "
                    "property or concept in this graph; a reading that needs a rebuild is a capability "
                    "limitation, not an alternative.",
                )

    keys: set[str] = set()
    for capability in context.capabilities:
        if not capability.key.strip() or capability.key in keys:
            error(capability.key, "Capabilities need unique, non-empty keys")
        keys.add(capability.key)
        if not capability.question.strip():
            error(capability.key, "State the question family this capability claims to answer")
        for concept in capability.concepts:
            problem = _resolve(concept, schema)
            if problem:
                error(capability.key, f"Capability depends on {problem}")

    for example in context.examples:
        if example.capability not in keys:
            error(example.capability, "A query example must name a declared capability")
        if not example.query.strip() or not example.language.strip():
            error(example.capability, "A query example needs a language and a runnable query")

    names: set[str] = set()
    for check in pipeline.validation_checks:
        if not check.name.strip() or check.name in names:
            error(check.name, "Validation checks need unique, non-empty names")
        names.add(check.name)
        if check.capability and check.capability not in keys:
            error(check.name, f"Validation check names undeclared capability {check.capability!r}")

    if not pipeline.validation_checks:
        warning(
            "context.unvalidated",
            pipeline.name,
            "No validation checks are declared. Definition and integrity checks cannot detect "
            "evidence the pipeline never emitted; declare checks that compare the graph with "
            "expectations derived from the sources.",
        )
    if not context.capabilities:
        warning(
            "context.no_capabilities",
            pipeline.name,
            "No question families are declared, so nothing states what this graph can answer.",
        )

    undescribed = sorted(c for c in schema if not _described(descriptions, c)["description"].strip())
    if undescribed:
        warning(
            "context.undescribed",
            "topology",
            "Concepts carry no authored description; a consumer sees only the label: " + ", ".join(undescribed),
        )
    missing = sorted(
        f"{concept}.{name}"
        for concept, item in descriptions.items()
        for name, text in item["properties"].items()
        if not text.strip()
    )
    if missing:
        warning(
            "context.undescribed_property",
            "topology",
            "Properties carry no authored description; their meaning is only their name: "
            + ", ".join(missing[:20])
            + (f" (+{len(missing) - 20} more)" if len(missing) > 20 else ""),
        )
    return findings


def build_query_context(
    pipeline: Pipeline,
    *,
    schema: dict[str, ConceptSchema],
    descriptions: dict[str, ConceptDescription],
    labels: dict[str, str],
    report: dict[str, Any],
) -> dict[str, Any]:
    """Generate the versioned context document from declarations and run evidence."""
    context = pipeline.query_context
    validation: dict[str, Any] = report.get("validation") or {}
    states: dict[str, Any] = validation.get("capabilities") or {}
    quality: dict[str, Any] = report.get("quality") or {}
    measurements: dict[str, Any] = quality.get("measurements") or {}
    population: dict[str, Any] = measurements.get("population") or {}
    emitted: list[dict[str, Any]] = report.get("findings") or []
    document: dict[str, Any] = {
        "schema_version": 1,
        "report_kind": "biotope.query_context",
        "generated": datetime.now(timezone.utc).isoformat(),
        "pipeline": pipeline.name,
        "scope": pipeline.scope,
        "guidance": GUIDANCE,
        "topology_digest": digest(schema),
        "concepts": {
            concept: {
                "label": labels[concept],
                "kind": item["kind"],
                "description": _described(descriptions, concept)["description"],
                "source": item["source"],
                "target": item["target"],
                "count": population.get(concept),
                "properties": {
                    name: {
                        "type": kind,
                        "nullable": name in item["nullable"],
                        "description": _described(descriptions, concept)["properties"].get(name, ""),
                    }
                    for name, kind in item["properties"].items()
                },
            }
            for concept, item in schema.items()
        },
        "interpretations": [
            {
                "subject": item.subject,
                "label": labels.get(_reference(item.subject, schema)[0], ""),
                "kind": item.kind,
                "statement": item.statement,
                "alternatives": list(item.alternatives),
            }
            for item in context.interpretations
        ],
        "capabilities": [
            {
                "key": item.key,
                "question": item.question,
                "concepts": list(item.concepts),
                "limitations": list(item.limitations),
                "state": states.get(item.key, {}).get("state", "unchecked"),
                "checks": states.get(item.key, {}).get("checks", []),
            }
            for item in context.capabilities
        ],
        "examples": [
            {
                "capability": item.capability,
                "language": item.language,
                "query": item.query,
                "expectation": item.expectation,
            }
            for item in context.examples
        ],
        "selection": {
            "policies": pipeline.policies,
            "exclusions": [
                {"policy": finding["policy"], "count": finding["count"]}
                for finding in emitted
                if finding.get("kind") == "exclusion"
            ],
            "audits": report.get("audits", []),
        },
        "validation": {
            "state": validation.get("state", "not_run"),
            "reason": validation.get("reason", "Validation did not run"),
            "checks": [
                {k: item[k] for k in ("name", "capability", "state", "detail", "evidence")}
                for item in validation.get("checks", [])
            ],
        },
        "settings": pipeline.settings,
        "variability": pipeline.variability,
        # Lists, not tuples: the in-memory document and the written file must be identical.
        "sources": [list(item) for item in report.get("source_versions", [])],
    }
    document["context_digest"] = digest({k: v for k, v in document.items() if k != "generated"})
    return document


def context_rows(document: dict[str, Any]) -> list[tuple[str, dict[str, object]]]:
    """Flatten the document into uniform rows for database-only delivery.

    One reserved label, one row shape, one fact per row, so a consumer with
    nothing but a Cypher session can select by ``entry`` or ``subject`` and
    recover every statement the JSON document carries. Text is escaped rather
    than reflowed: a query returned from here runs unchanged after decoding.
    """
    rows: list[tuple[str, dict[str, object]]] = []
    selection: dict[str, Any] = document["selection"]
    policies: dict[str, str] = selection["policies"]
    validation: dict[str, Any] = document["validation"]

    def add(entry: str, subject: str, statement: object, detail: object = "", label: str = "") -> None:
        values = {"entry": entry, "subject": subject, "label": label, "statement": statement, "detail": detail}
        rows.append(
            (
                f"{CONTEXT_CONCEPT}:{len(rows):05d}",
                {name: encode_text(str(value)) for name, value in values.items()},
            )
        )

    add("guidance", document["pipeline"], document["guidance"], document["scope"])
    add("encoding", document["pipeline"], ENCODING)
    add("variability", document["pipeline"], document["variability"])

    for concept, item in document["concepts"].items():
        measured = "unmeasured" if item["count"] is None else item["count"]
        add("concept", concept, item["description"], f"{item['kind']}; records: {measured}", item["label"])
        for endpoint in ("source", "target"):
            if item[endpoint] is not None:
                add(f"concept_{endpoint}", concept, item[endpoint])
        for name, prop in item["properties"].items():
            detail = f"{prop['type']}{', nullable' if prop['nullable'] else ''}"
            add("property", f"{concept}.{name}", prop["description"], detail, item["label"])

    for item in document["interpretations"]:
        add(item["kind"], item["subject"], item["statement"], label=item["label"])
        for alternative in item["alternatives"]:
            add("alternative", item["subject"], alternative, "also queryable")

    for item in document["capabilities"]:
        add("capability", item["key"], item["question"], item["state"])
        for concept in item["concepts"]:
            add("capability_concept", item["key"], concept)
        for name in item["checks"]:
            add("capability_check", item["key"], name)
        for limitation in item["limitations"]:
            add("capability_limit", item["key"], limitation)

    for item in document["examples"]:
        add("example", item["capability"], item["query"], item["expectation"], item["language"])

    add("validation", document["pipeline"], validation["reason"], validation["state"])
    for item in validation["checks"]:
        add("check", item["name"], item["detail"], item["state"], item["capability"])
        for line in item["evidence"]:
            add("check_evidence", item["name"], line)

    for item in selection["exclusions"]:
        add("exclusion", item["policy"], policies.get(item["policy"], ""), f"{item['count']} records excluded")
    for item in selection["audits"]:
        add("audit", item["stage"], item["selection"], f"{item['inputs']} -> {item['outputs']}")
        for name, count in sorted(item["counts"].items()):
            add("audit_count", item["stage"], count, label=name)
        for note in item["notes"]:
            add("audit_note", item["stage"], note)

    for artifact, version in document["sources"]:
        add("source", artifact, version)
    for name, value in sorted(document["settings"].items()):
        add("setting", name, value)
    return rows
