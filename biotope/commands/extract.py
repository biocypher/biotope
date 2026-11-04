from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, NoReturn, cast

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from biotope.commands._add_output import AddOutput
from biotope.commands.add import add_file
from biotope.croissant import annotation
from biotope.croissant.ids import stem, table_id
from biotope.extraction import Extraction, Schema
from biotope.extraction.describe import describe
from biotope.extraction.run import (
    Outcome,
    Source,
    described_files,
    document_status,
    extract_all,
    failure,
    identity,
    placeholders,
    records_path,
    run,
    sha256,
    sources,
    state_path,
)
from biotope.graph.sources import refresh_description, write_description
from biotope.graph.workspace import Workspace, select_workspace
from biotope.metadata import FILE_OBJECT_TYPE, STATUS_PROCESSED, get_derived_from, manifest_for
from biotope.utils import find_biotope_root, ignored_by_git, unreported


class Output:
    def __init__(self, as_json: bool) -> None:
        self.as_json = as_json
        self.console = Console(stderr=True, highlight=False)
        self.report: dict[str, Any] = {"schema_version": 2, "status": "complete"}

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


@click.group(help="Extract records from documents with the extractions listed in graph/extraction/__init__.py.")
def extract_group() -> None:
    pass


@extract_group.command(
    "try",
    help="Run the extraction NAME on FILES and show the records with their evidence. Nothing in the project "
    "changes.",
)
@click.argument("name")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Write one JSON report to stdout")
def try_command(name: str, files: tuple[Path, ...], as_json: bool) -> None:
    output = Output(as_json)
    root = _root(output)
    paths = [_project_path(root, file) for file in files]
    with select_workspace(_graph(output, root)) as workspace:
        [extraction] = _chosen(output, root, _listed(output, workspace), (name,))
        schema = _schema(output, extraction)
        named = identity(extraction.extractor)
        output.report.update(extraction=extraction.name, schema=_schema_report(schema), extractor=named, documents=[])
        _header(output, "Try", extraction.name, schema, named)
        try:
            described = described_files(root)
        except ValueError as exc:
            output.fail(str(exc))
        work = [(number, described.get(path, Source(path, path, ""))) for number, path in enumerate(paths, 1)]
        done = {
            work[index][1].path: extracted
            for index, extracted in extract_all(
                extraction, schema, root, work, len(paths), frozenset(), output.progress
            )
        }
    failed = False
    documents: list[dict[str, Any]] = []
    output.report["documents"] = documents
    for path in paths:
        extracted = done[path]
        if isinstance(extracted, BaseException):
            failed = True
            reason = failure(extracted)
            documents.append({"path": path, "status": "failed", "records": [], "reason": reason})
            output.row("FAIL", path, reason)
            continue
        status = document_status(extracted)
        documents.append({"path": path, "status": status, "records": extracted})
        output.row("OK" if extracted else "WARN", path, f"{status}, {_count(len(extracted))}")
        for record in extracted:
            output.row("Record", record["id"], _shown(record))
    output.finish(failed)


@extract_group.command(
    "run",
    help="Run the extractions NAMES, or every listed extraction, store their records in "
    "data/extracted/<name>.jsonl and register each as a processed dataset. Records mirror the files the "
    "extraction's patterns match now; unchanged documents reuse their stored records.",
)
@click.argument("names", nargs=-1)
@click.option(
    "--redo",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Extract this document again although its inputs are unchanged; repeatable",
)
@click.option("--json", "as_json", is_flag=True, help="Write one JSON report to stdout")
def run_command(names: tuple[str, ...], redo: tuple[Path, ...], as_json: bool) -> None:
    output = Output(as_json)
    root = _root(output)
    chosen_redo = frozenset(_project_path(root, file) for file in redo)
    reports: list[dict[str, Any]] = []
    output.report["extractions"] = reports
    failed = False
    with select_workspace(_graph(output, root)) as workspace:
        chosen = _chosen(output, root, _listed(output, workspace), names)
        try:
            described = described_files(root)
            plans = [
                (extraction, _schema(output, extraction), sources(root, extraction, described)) for extraction in chosen
            ]
        except ValueError as exc:
            output.fail(str(exc))
        strangers = sorted(chosen_redo - {source.path for _, _, found in plans for source in found})
        if strangers:
            output.fail(f"{', '.join(strangers)} is not a document of {', '.join(item.name for item in chosen)}")
        if not plans:
            output.row("WARN", "no extractions", "graph/extraction/__init__.py lists none.")
        for extraction, schema, found in plans:
            report, problem = _run_one(output, root, extraction, schema, found, chosen_redo)
            reports.append(report)
            failed = failed or problem
    output.finish(failed)


def _run_one(
    output: Output, root: Path, extraction: Extraction, schema: Schema, found: list[Source], redo: frozenset[str]
) -> tuple[dict[str, Any], bool]:
    target = records_path(root, extraction.name)
    relative = target.relative_to(root).as_posix()
    named = identity(extraction.extractor)
    _header(output, "Extract", f"{extraction.name} -> {relative}", schema, named)
    result = run(root, extraction, schema, found, redo, output.progress)
    dataset_ids = sorted({source.dataset for source in found})
    manifest = manifest_for(target, root)
    if not _registered(root, target, manifest, schema, dataset_ids, result.records):
        _register(root, target, manifest, schema, dataset_ids, result.records)
    ignored = ignored_by_git(root, [target, manifest, state_path(root, extraction.name)])
    report = {
        "name": extraction.name,
        "schema": _schema_report(schema),
        "extractor": named,
        "output": relative,
        "manifest": manifest.relative_to(root).as_posix(),
        "documents": [_document_report(outcome) for outcome in result.documents],
        "appeared": result.appeared,
        "disappeared": result.disappeared,
        "moved": result.moved,
        "ignored": ignored,
    }
    for outcome in result.documents:
        label = "FAIL" if outcome.status == "failed" else "OK" if outcome.records else "WARN"
        detail = f"{outcome.status}, {_count(outcome.records)}"
        if outcome.moved_from:
            detail += f", moved from {outcome.moved_from}"
        if outcome.reason:
            detail += f"\n{outcome.reason}"
        output.row(label, outcome.path, detail)
    for pair in result.moved:
        output.row("Moved", pair["from"], f"now {pair['to']}")
    for record_id in result.disappeared:
        output.row("Gone", record_id)
    for record_id in result.appeared:
        output.row("New", record_id)
    output.row("Saved", relative, f"registered as {manifest.relative_to(root).as_posix()}")
    for path in unreported(root, ignored):
        output.row("WARN", f"git ignores {path}", "Commit it with the project: add an exception to .gitignore.")
    return report, any(outcome.status == "failed" for outcome in result.documents)


def _root(output: Output) -> Path:
    root = find_biotope_root()
    if root is None:
        output.fail("Not in a biotope project. Run 'biotope init' first.")
    return root


def _graph(output: Output, root: Path) -> Path:
    graph = root / "graph"
    if not (graph / "__init__.py").is_file():
        output.fail(f"No graph workspace at {graph}; run biotope graph scaffold")
    return graph


def _listed(output: Output, workspace: Workspace) -> tuple[Extraction, ...]:
    try:
        return workspace.extractions()
    except Exception as exc:
        output.fail(f"graph/extraction: {type(exc).__name__}: {exc}")


def _chosen(output: Output, root: Path, listed: tuple[Extraction, ...], names: tuple[str, ...]) -> list[Extraction]:
    by_name = {extraction.name: extraction for extraction in listed}
    unknown = [name for name in names if name not in by_name]
    if unknown:
        known = ", ".join(by_name) or "none"
        output.fail(f"graph/extraction/__init__.py lists no extraction {', '.join(unknown)}; it lists {known}")
    chosen = [by_name[name] for name in dict.fromkeys(names)] if names else list(listed)
    for extraction in chosen:
        files = placeholders(extraction)
        if files:
            shown = ", ".join(_project_path(root, file) for file in files)
            output.fail(f"{extraction.name}: {shown} is still a placeholder; fill it in and delete its first line")
    return chosen


def _schema(output: Output, extraction: Extraction) -> Schema:
    try:
        return Schema.from_class(extraction.schema)
    except ValueError as exc:
        output.fail(str(exc))


def _count(records: int) -> str:
    return f"{records} {'record' if records == 1 else 'records'}"


def _register(
    root: Path, target: Path, manifest: Path, schema: Schema, dataset_ids: list[str], records: list[dict[str, Any]]
) -> None:
    overrides = {
        "name": target.relative_to(root).as_posix(),
        "description": f"{schema.name} records extracted from {', '.join(dataset_ids)}. {schema.description}".strip(),
        "status_override": STATUS_PROCESSED,
        "derived_from": dataset_ids,
    }
    datasets_dir = root / ".biotope/datasets"
    if not add_file(target, root, datasets_dir, True, overrides, reporter=AddOutput(as_json=True)):
        raise click.ClickException(f"{target} could not be registered")
    metadata = annotation.restored(refresh_description(manifest))
    file_object = _file_object(root, target, metadata)
    if file_object is None:
        raise click.ClickException(f"{manifest} does not list {target}")
    describe(metadata, schema, file_object["@id"], table_id(file_object["@id"], stem(target.name)), records)
    write_description(manifest, metadata)


def _registered(
    root: Path, target: Path, manifest: Path, schema: Schema, dataset_ids: list[str], records: list[dict[str, Any]]
) -> bool:
    if not manifest.is_file():
        return False
    metadata = annotation.restored(refresh_description(manifest))
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


def _schema_report(schema: Schema) -> dict[str, Any]:
    return {"name": schema.name, "revision": schema.revision, "key": list(schema.key)}


def _header(output: Output, label: str, subject: str, schema: Schema, named: dict[str, Any]) -> None:
    settings = ", ".join(f"{key}={value}" for key, value in named["settings"].items())
    detail = f"{schema.name}, schema revision {schema.revision[:12]}; {named['name']} {named['version']} {settings}"
    output.row(label, subject, detail.rstrip())


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
            if evidence["quote"] is not None:
                lines.append(f"  {json.dumps(evidence['quote'], ensure_ascii=False)}")
            if evidence["locator"] is not None:
                lines.append(f"  at {evidence['locator']}")
    return "\n".join(lines)
