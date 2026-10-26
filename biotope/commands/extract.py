from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, NoReturn, cast

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.text import Text

from biotope.commands._add_output import AddOutput
from biotope.commands.add import add_file, default_overrides, resolve_dataset_ref
from biotope.croissant.ids import stem, table_id
from biotope.extraction import ExtractionError, Extractor, Schema
from biotope.extraction.describe import describe
from biotope.extraction.run import (
    PROGRESS,
    STATES,
    Outcome,
    Review,
    Source,
    document_status,
    extract_all,
    failure,
    identity,
    load_extractor,
    parallelism,
    review,
    run,
    sha256,
)
from biotope.extraction.text import convert, media_type
from biotope.graph.sources import write_text_atomic
from biotope.metadata import (
    FILE_OBJECT_TYPE,
    STATUS_PROCESSED,
    dataset_dir_for_manifest,
    get_derived_from,
    resolve_content_url,
)
from biotope.utils import find_biotope_root, ignored_by_git


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

    def progress(self, number: int, total: int, path: str) -> None:
        click.echo(f"Extracting {number}/{total} {path}", err=True)

    def fail(self, message: str) -> NoReturn:
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
    root, schema, extractor, parallel = _prepare(output, schema_ref)
    named = identity(extractor)
    output.report.update(schema=_schema_report(schema), extractor=named, documents=[])
    _header(output, "Try", schema, named)
    paths = [_project_path(root, file) for file in files]
    work = [(number, Source(path, kind)) for number, path in enumerate(paths, 1) if (kind := media_type(path))]
    done = {
        work[index][1].path: extracted
        for index, extracted in extract_all(
            extractor, schema, root, work, len(paths), None, frozenset(), parallel, output.progress
        )
    }
    failed = False
    documents: list[dict[str, Any]] = []
    output.report["documents"] = documents
    for path in paths:
        extracted = done.get(path, ExtractionError("not a PDF, HTML, text or Markdown document"))
        if isinstance(extracted, BaseException):
            failed = True
            reason = failure(extracted)
            documents.append({"path": path, "status": "failed", "records": [], "reason": reason})
            output.row("FAIL", path, reason)
            continue
        status, reason = document_status(extracted)
        entry = {"path": path, "status": status, "records": extracted}
        documents.append({**entry, "reason": reason} if reason else entry)
        label = "OK" if status == "extracted" else "WARN"
        output.row(label, path, f"{status}, {_count(len(extracted))}" + (f"\n{reason}" if reason else ""))
        for record in extracted:
            output.row("Record", record["id"], _shown(record))
    if any(not isinstance(extracted, BaseException) for extracted in done.values()):
        marker = _tried(schema)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    _review(output, review([record for entry in documents for record in entry["records"]]))
    output.finish(failed)


@extract_group.command(
    "run",
    help="Extract the documents of the registered DATASETS under SCHEMA (path/to/module.py:Class), store the "
    "records and register them as a processed dataset. Unchanged documents reuse their stored records.",
)
@click.argument("schema_ref", metavar="SCHEMA")
@click.argument("datasets", nargs=-1, required=True)
@click.option(
    "--out", type=click.Path(dir_okay=False, path_type=Path), help="Records file [data/extracted/<schema>.jsonl]"
)
@click.option(
    "--redo",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Extract this document again although its inputs are unchanged; repeatable",
)
@click.option("--json", "as_json", is_flag=True, help="Write one JSON report to stdout")
def run_command(
    schema_ref: str, datasets: tuple[str, ...], out: Path | None, redo: tuple[Path, ...], as_json: bool
) -> None:
    output = Output(as_json)
    root, schema, extractor, parallel = _prepare(output, schema_ref)
    try:
        dataset_ids = [resolve_dataset_ref(reference, root) for reference in datasets]
    except ValueError as exc:
        output.fail(str(exc).replace("--derived-from ", ""))
    sources = _sources(root, dataset_ids)
    chosen = frozenset(_project_path(root, file) for file in redo)
    strangers = sorted(chosen - {source.path for source in sources})
    if strangers:
        output.fail(f"{', '.join(strangers)} is not a document of {', '.join(datasets)}")
    target = out.resolve() if out is not None else root / "data/extracted" / f"{_snake(schema.name)}.jsonl"
    try:
        relative = target.relative_to(root)
    except ValueError:
        output.fail(f"{out} is outside the project")
    named = identity(extractor)
    output.report.update(schema=_schema_report(schema), extractor=named, output=relative.as_posix())
    _header(output, "Extract", schema, named, relative.as_posix())
    warnings: list[str] = []
    output.report["warnings"] = warnings
    if not _tried(schema).is_file():
        warning = (
            f"Schema revision {schema.revision[:12]} of {schema.name} was never shown with biotope extract try "
            "on this machine. Run try on sample documents and have the user approve the records before a full run."
        )
        warnings.append(warning)
        output.row("WARN", "untried schema", warning)
    state = root / STATES / relative.with_suffix(".json")
    progress = root / PROGRESS / relative
    result = run(root, schema, extractor, sources, target, state, progress, chosen, output.progress, parallel)
    manifest = root / ".biotope/datasets" / relative.with_suffix(".jsonld")
    if not _registered(root, target, manifest, schema, dataset_ids, result.records):
        _register(root, target, manifest, schema, dataset_ids, result.records)
    ignored = ignored_by_git(root, [target, manifest, state])
    output.report.update(
        manifest=manifest.relative_to(root).as_posix(),
        documents=[_document_report(outcome) for outcome in result.documents],
        appeared=result.appeared,
        disappeared=result.disappeared,
        moved=result.moved,
        ignored=ignored,
    )
    for outcome in result.documents:
        label = (
            "FAIL"
            if outcome.status in {"failed", "missing"}
            else "OK"
            if outcome.records and outcome.status != "unsupported"
            else "WARN"
        )
        detail = f"{outcome.status}, {_count(outcome.records)}"
        if outcome.moved_from:
            detail += f", moved from {outcome.moved_from}"
        if outcome.reason:
            detail += f"\n{outcome.reason}"
        output.row(label, outcome.path, detail)
    _review(output, review(result.records))
    for pair in result.moved:
        output.row("Moved", pair["from"], f"now {pair['to']}")
    for record_id in result.disappeared:
        output.row("Gone", record_id)
    for record_id in result.appeared:
        output.row("New", record_id)
    output.row("Saved", relative.as_posix(), f"registered as {manifest.relative_to(root).as_posix()}")
    for path in ignored:
        output.row("WARN", f"git ignores {path}", "Commit it with the project: add an exception to .gitignore.")
    output.finish(any(outcome.status in {"failed", "missing"} for outcome in result.documents))


@extract_group.command(
    "text",
    help="Print biotope's text of FILE: what an extractor reads, and what evidence offsets and pages refer to. "
    "PDF pages are separated by a form feed.",
)
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def text_command(file: Path) -> None:
    kind = media_type(file.name)
    if kind is None:
        raise click.ClickException(f"{file} is not a PDF, HTML, text or Markdown document")
    click.echo(convert(file, kind), nl=False)


@extract_group.command(
    "schema",
    help="Print the JSON Schema biotope derives from SCHEMA (path/to/module.py:Class), with the schema's name, "
    "record key and revision, as JSON.",
)
@click.argument("schema_ref", metavar="SCHEMA")
def schema_command(schema_ref: str) -> None:
    try:
        schema = Schema.load(schema_ref, find_biotope_root() or Path.cwd())
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    described = {**_schema_report(schema), "json_schema": schema.json_schema()}
    click.echo(json.dumps(described, indent=2, ensure_ascii=False))


def _count(records: int) -> str:
    return f"{records} {'record' if records == 1 else 'records'}"


def _review(output: Output, found: Review) -> None:
    counts = dict(found.counts)
    output.report.update(counts=counts, unaligned=found.unaligned, weak=found.weak, unsupported=found.unsupported)
    output.row(
        "Values",
        f"{counts['values']} non-null",
        f"{counts['aligned']} aligned, {counts['unaligned']} unaligned, {counts['weak']} weak",
    )
    for item in found.unaligned:
        problem = (
            "no quote or locator" if item["quote"] is None else f"quote not found in the document: {item['quote']!r}"
        )
        output.row("WARN", item["record"], f"{item['field']}: {problem}")
    for item in found.weak:
        output.row("Weak", item["record"], f"{item['field']}: {' and '.join(item['reasons'])} quote {item['quote']!r}")
    for item in found.unsupported:
        output.row(
            "Review",
            item["record"],
            f"unsupported: {item['unaligned']} of {item['values']} values have no aligned evidence, "
            f"{item['running_head']} are found only in running heads",
        )


def _tried(schema: Schema) -> Path:
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return cache / "biotope/tried" / schema.revision


def _prepare(output: Output, schema_ref: str) -> tuple[Path, Schema, Extractor, int]:
    root = find_biotope_root()
    if root is None:
        output.fail("Not in a biotope project. Run 'biotope init' first.")
    config_path = root / ".biotope/config.yaml"
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.is_file() else None
    config = cast(dict[str, Any], loaded or {})
    try:
        schema = Schema.load(schema_ref, root)
        extractor = load_extractor(root, config)
        parallel = parallelism(config)
    except Exception as exc:
        output.fail(str(exc))
    return root, schema, extractor, parallel


def _sources(root: Path, dataset_ids: list[str]) -> list[Source]:
    found: dict[str, Source] = {}
    for dataset_id in dataset_ids:
        manifest = root / ".biotope/datasets" / f"{dataset_id}.jsonld"
        metadata = cast(dict[str, Any], json.loads(manifest.read_text(encoding="utf-8")))
        dataset_dir = dataset_dir_for_manifest(manifest, root)
        for entry in cast(list[dict[str, Any]], metadata.get("distribution") or []):
            url = entry.get("contentUrl")
            if entry.get("@type") != FILE_OBJECT_TYPE or not isinstance(url, str):
                continue
            kind = media_type(url)
            if kind is None:
                continue
            located = resolve_content_url(url, dataset_dir, root)
            if located is None:
                located = (
                    root / url if (root / url).resolve().is_relative_to(dataset_dir.resolve()) else dataset_dir / url
                )
            path = located.resolve().relative_to(root).as_posix()
            found.setdefault(path, Source(path, kind))
    return [found[path] for path in sorted(found)]


def _register(
    root: Path, target: Path, manifest: Path, schema: Schema, dataset_ids: list[str], records: list[dict[str, Any]]
) -> None:
    overrides = {
        **default_overrides(),
        "name": target.relative_to(root).as_posix(),
        "description": f"{schema.name} records extracted from {', '.join(dataset_ids)}. {schema.description}".strip(),
        "status_override": STATUS_PROCESSED,
        "derived_from": dataset_ids,
    }
    datasets_dir = root / ".biotope/datasets"
    if not add_file(target, root, datasets_dir, True, overrides, reporter=AddOutput(as_json=True)):
        raise click.ClickException(f"{target} could not be registered")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    file_object = _file_object(root, target, metadata)
    if file_object is None:
        raise click.ClickException(f"{manifest} does not list {target}")
    describe(metadata, schema, file_object["@id"], table_id(file_object["@id"], stem(target.name)), records)
    write_text_atomic(manifest, json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")


def _registered(
    root: Path, target: Path, manifest: Path, schema: Schema, dataset_ids: list[str], records: list[dict[str, Any]]
) -> bool:
    if not manifest.is_file():
        return False
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    file_object = _file_object(root, target, metadata)
    if file_object is None or file_object.get("sha256") != sha256(target) or get_derived_from(metadata) != dataset_ids:
        return False
    described = copy.deepcopy(metadata)
    describe(described, schema, file_object["@id"], table_id(file_object["@id"], stem(target.name)), records)
    return described == metadata


def _file_object(root: Path, target: Path, metadata: dict[str, Any]) -> dict[str, Any] | None:
    relative = target.relative_to(root).as_posix()
    entries = cast(list[dict[str, Any]], metadata.get("distribution", []))
    return next(
        (entry for entry in entries if entry.get("@type") == FILE_OBJECT_TYPE and entry.get("contentUrl") == relative),
        None,
    )


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


def _document_report(outcome: Outcome) -> dict[str, Any]:
    report = {"path": outcome.path, "status": outcome.status, "records": outcome.records, "sha256": outcome.sha256}
    if outcome.reason:
        report["reason"] = outcome.reason
    if outcome.moved_from:
        report["moved_from"] = outcome.moved_from
    return report


def _shown(record: dict[str, Any]) -> str:
    lines: list[str] = []
    for name, given in cast(dict[str, Any], record["values"]).items():
        for item in cast(list[dict[str, Any]], given if isinstance(given, list) else [given]):
            lines.append(f"{name}: {json.dumps(item['value'], ensure_ascii=False)}")
            evidence = item["evidence"]
            if evidence is None:
                if item["value"] is not None:
                    lines.append("  no quote or locator")
                continue
            if evidence["locator"] is not None:
                lines.append(f"  at {evidence['locator']}")
                continue
            where = "unaligned"
            if evidence["aligned"]:
                where = f"characters {evidence['start']}-{evidence['end']}"
                if evidence["page"] is not None:
                    where = f"page {evidence['page']}, {where}"
                reasons = cast(list[str], evidence["weak"])
                if reasons:
                    found = f"found {evidence['occurrences']} times"
                    where += f"; weak: {', '.join(found if reason == 'repeated' else reason for reason in reasons)}"
            lines.append(f"  {json.dumps(evidence['quote'], ensure_ascii=False)} ({where})")
    return "\n".join(lines)
