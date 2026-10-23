from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.text import Text

from biotope.commands._add_output import AddOutput
from biotope.commands.add import _add_file, _resolve_dataset_ref
from biotope.extraction import Document, Schema
from biotope.extraction.describe import describe
from biotope.extraction.run import (
    STATES,
    Source,
    document_text,
    extract_document,
    identity,
    load_extractor,
    run,
    sha256,
)
from biotope.extraction.text import media_type
from biotope.graph.sources import write_text_atomic
from biotope.metadata import (
    FILE_OBJECT_TYPE,
    STATUS_PROCESSED,
    dataset_dir_for_manifest,
    get_derived_from,
    resolve_content_url,
)
from biotope.utils import find_biotope_root, stage_git_changes


class Output:
    def __init__(self, as_json: bool) -> None:
        self.as_json = as_json
        self.console = Console(stderr=True, highlight=False)
        self.report: dict[str, Any] = {"schema_version": 1, "status": "complete"}

    def row(self, label: str, value: str, detail: str = "") -> None:
        if self.as_json:
            return
        colour = {"OK": "green", "WARN": "yellow", "FAIL": "red"}.get(label, "")
        table = Table.grid(padding=0)
        table.add_column(width=9, min_width=9, max_width=9, no_wrap=True)
        table.add_column(overflow="fold")
        table.add_row(Text(label, style=f"bold {colour}".strip()), Text(value))
        for line in detail.splitlines():
            table.add_row("", Text(line, style="dim"))
        self.console.print(table)

    def fail(self, message: str) -> None:
        if self.as_json:
            self.report.update(status="error", error=message)
            click.echo(json.dumps(self.report, indent=2, ensure_ascii=False))
            sys.exit(1)
        raise click.ClickException(message)

    def finish(self, failed: bool) -> None:
        if failed:
            self.report["status"] = "failed"
        if self.as_json:
            click.echo(json.dumps(self.report, indent=2, ensure_ascii=False))
        if failed:
            sys.exit(1)


@click.group(help="Turn local documents into stored records under a reviewed extraction schema.")
def extract_group() -> None:
    pass


@extract_group.command(
    "try",
    help="Run the configured extractor with SCHEMA (path/to/module.py:Class) on FILES and show the records with "
    "their evidence. Nothing in the project changes.",
)
@click.argument("schema_ref", metavar="SCHEMA")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Write one JSON report to stdout")
def try_command(schema_ref: str, files: tuple[Path, ...], as_json: bool) -> None:
    output = Output(as_json)
    root, schema, extractor = _prepare(output, schema_ref)
    named = identity(extractor)
    output.report.update(schema=_schema_report(schema), extractor=named, documents=[])
    _header(output, "Try", schema, named)
    failed = False
    for file in files:
        path = _project_path(root, file)
        entry: dict[str, Any] = {"path": path, "status": "extracted", "records": []}
        output.report["documents"].append(entry)
        kind = media_type(path)
        try:
            if kind is None:
                raise ValueError("not a PDF, HTML, text or Markdown document")
            digest = sha256(file)
            provenance = {"document_sha256": digest, "media_type": kind, "schema": schema.name}
            provenance.update(schema_revision=schema.revision, extractor=named)
            document = Document(path, digest, kind, document_text(file, kind, digest, None))
            entry["records"] = extract_document(extractor, schema, document, provenance)
        except Exception as exc:
            failed = True
            entry.update(status="failed", reason=str(exc))
            output.row("FAIL", path, str(exc))
            continue
        count = len(entry["records"])
        output.row("OK", path, f"{count} {'record' if count == 1 else 'records'}")
        for record in entry["records"]:
            output.row("Record", record["id"], _shown(record))
    output.finish(failed)


@extract_group.command(
    "run",
    help="Extract the documents of the registered DATASETS under SCHEMA (path/to/module.py:Class), store the "
    "records and register them as a processed dataset. Unchanged documents reuse their stored records.",
)
@click.argument("schema_ref", metavar="SCHEMA")
@click.argument("datasets", nargs=-1, required=True)
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), help="Records file [extracted/<schema>.jsonl]")
@click.option("--json", "as_json", is_flag=True, help="Write one JSON report to stdout")
def run_command(schema_ref: str, datasets: tuple[str, ...], out: Path | None, as_json: bool) -> None:
    output = Output(as_json)
    root, schema, extractor = _prepare(output, schema_ref)
    try:
        dataset_ids = [_resolve_dataset_ref(reference, root) for reference in datasets]
    except ValueError as exc:
        output.fail(str(exc).replace("--derived-from ", ""))
        return
    sources = _sources(root, dataset_ids)
    target = (out if out is not None else Path("extracted") / f"{_snake(schema.name)}.jsonl").resolve()
    try:
        relative = target.relative_to(root)
    except ValueError:
        output.fail(f"{out} is outside the project")
        return
    named = identity(extractor)
    output.report.update(schema=_schema_report(schema), extractor=named, output=relative.as_posix())
    _header(output, "Extract", schema, named, relative.as_posix())
    result = run(root, schema, extractor, sources, target, root / STATES / relative.with_suffix(".json"))
    manifest = root / ".biotope/datasets" / relative.with_suffix(".jsonld")
    if result.changed or not manifest.is_file() or _derived(manifest) != dataset_ids:
        _register(root, target, manifest, schema, dataset_ids, result.records)
    output.report.update(
        manifest=manifest.relative_to(root).as_posix(),
        documents=[_document_report(outcome) for outcome in result.documents],
        unaligned=result.unaligned,
        appeared=result.appeared,
        disappeared=result.disappeared,
        moved=result.moved,
    )
    for outcome in result.documents:
        label = "OK" if outcome.status in {"extracted", "reused"} else "FAIL"
        count = f"{outcome.records} {'record' if outcome.records == 1 else 'records'}"
        detail = f"{outcome.status}, {count}"
        if outcome.moved_from:
            detail += f", moved from {outcome.moved_from}"
        if outcome.reason:
            detail += f"\n{outcome.reason}"
        output.row(label, outcome.path, detail)
    for item in result.unaligned:
        output.row("WARN", item["record"], f"{item['field']}: quote not found in the document: {item['quote']!r}")
    for pair in result.moved:
        output.row("Moved", pair["from"], f"now {pair['to']}")
    for record_id in result.disappeared:
        output.row("Gone", record_id)
    for record_id in result.appeared:
        output.row("New", record_id)
    output.row("Saved", relative.as_posix(), f"registered as {manifest.relative_to(root).as_posix()}")
    output.finish(any(outcome.status in {"failed", "missing"} for outcome in result.documents))


def _prepare(output: Output, schema_ref: str):
    root = find_biotope_root()
    if root is None:
        output.fail("Not in a biotope project. Run 'biotope init' first.")
        raise SystemExit(1)
    config_path = root / ".biotope/config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    try:
        schema = Schema.load(schema_ref, root)
        extractor = load_extractor(root, config or {})
    except Exception as exc:
        output.fail(str(exc))
        raise SystemExit(1) from exc
    return root, schema, extractor


def _sources(root: Path, dataset_ids: list[str]) -> list[Source]:
    found: dict[str, Source] = {}
    for dataset_id in dataset_ids:
        manifest = root / ".biotope/datasets" / f"{dataset_id}.jsonld"
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        dataset_dir = dataset_dir_for_manifest(manifest, root)
        for entry in metadata.get("distribution", []) or []:
            url = entry.get("contentUrl")
            if entry.get("@type") != FILE_OBJECT_TYPE or not isinstance(url, str):
                continue
            kind = media_type(url, entry.get("encodingFormat"))
            if kind is None:
                continue
            located = resolve_content_url(url, dataset_dir, root)
            path = located.resolve().relative_to(root).as_posix() if located is not None else Path(url).as_posix()
            found.setdefault(path, Source(path, kind))
    return [found[path] for path in sorted(found)]


def _register(
    root: Path, target: Path, manifest: Path, schema: Schema, dataset_ids: list[str], records: list[dict[str, Any]]
) -> None:
    overrides = {
        "name": target.relative_to(root).as_posix(),
        "description": f"{schema.name} records extracted from {', '.join(dataset_ids)}. {schema.description}".strip(),
        "license": None,
        "creator": None,
        "creator_email": None,
        "url": None,
        "citation": None,
        "version": None,
        "keywords": [],
        "access_restrictions": None,
        "legal_obligations": None,
        "collaboration_partner": None,
        "rai_fields": {},
        "status_override": STATUS_PROCESSED,
        "derived_from": dataset_ids,
    }
    datasets_dir = root / ".biotope/datasets"
    if not _add_file(target, root, datasets_dir, True, overrides, reporter=AddOutput(as_json=True)):
        raise click.ClickException(f"{target} could not be registered")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    relative = target.relative_to(root).as_posix()
    file_id = next(
        entry["@id"]
        for entry in metadata.get("distribution", [])
        if entry.get("@type") == FILE_OBJECT_TYPE and entry.get("contentUrl") == relative
    )
    describe(metadata, schema, file_id, target.name, records)
    write_text_atomic(manifest, json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    stage_git_changes(root)


def _derived(manifest: Path) -> list[str]:
    return get_derived_from(json.loads(manifest.read_text(encoding="utf-8")))


def _project_path(root: Path, file: Path) -> str:
    resolved = file.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.as_posix()


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _schema_report(schema: Schema) -> dict[str, Any]:
    return {"name": schema.name, "revision": schema.revision, "key": list(schema.key)}


def _header(output: Output, label: str, schema: Schema, named: dict[str, Any], target: str = "") -> None:
    settings = ", ".join(f"{key}={value}" for key, value in named["settings"].items())
    subject = f"{schema.name} -> {target}" if target else schema.name
    output.row(label, subject, f"schema revision {schema.revision[:12]}; {named['name']} {named['version']} {settings}")


def _document_report(outcome: Any) -> dict[str, Any]:
    report = {"path": outcome.path, "status": outcome.status, "records": outcome.records, "sha256": outcome.sha256}
    if outcome.reason:
        report["reason"] = outcome.reason
    if outcome.moved_from:
        report["moved_from"] = outcome.moved_from
    return report


def _shown(record: dict[str, Any]) -> str:
    lines: list[str] = []
    for name, given in record["values"].items():
        for item in given if isinstance(given, list) else [given]:
            lines.append(f"{name}: {json.dumps(item['value'], ensure_ascii=False)}")
            evidence = item["evidence"]
            if evidence is None:
                continue
            if evidence["locator"] is not None:
                lines.append(f"  at {evidence['locator']}")
                continue
            where = "unaligned"
            if evidence["aligned"]:
                where = f"characters {evidence['start']}-{evidence['end']}"
                if evidence["page"] is not None:
                    where = f"page {evidence['page']}, {where}"
            lines.append(f"  {json.dumps(evidence['quote'], ensure_ascii=False)} ({where})")
    return "\n".join(lines)
