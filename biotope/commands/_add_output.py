"""Terminal presentation and JSON reports for ``add``; no source-data access."""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text


class AddOutput:
    """Keep complete scan evidence separate from its human presentation."""

    def __init__(self, as_json: bool = False, *, console: Console | None = None) -> None:
        self.as_json = as_json
        self.console = console or Console(stderr=True)
        self.root = Path.cwd()
        self.sources: list[dict[str, Any]] = []

    def __enter__(self):
        # Upstream print() calls and legacy command messages must never corrupt JSON.
        self._redirect = redirect_stdout(sys.stderr)
        self._redirect.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback):
        sys.stderr.flush()
        self._redirect.__exit__(exc_type, exc, traceback)
        if self.as_json:
            status = "complete"
            if exc is not None or any(s["status"] == "failed" for s in self.sources):
                status = "failed"
            elif self.sources and all(s["status"] == "skipped" for s in self.sources):
                status = "unchanged"
            elif any(s.get("scan", {}).get("undescribed") or s.get("diagnostics") for s in self.sources):
                status = "complete_with_gaps"
            report = {
                "schema_version": 1,
                "project_root": str(self.root),
                "status": status,
                "sources": self.sources,
            }
            if exc is not None:
                report["error"] = str(exc)
            click.echo(json.dumps(report, indent=2, ensure_ascii=False))

    def path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root))
        except ValueError:
            return str(path.resolve())

    def row(self, label: str, value: str, detail: str = "") -> None:
        if self.as_json:
            return
        colour = {"OK": "green", "WARN": "yellow", "SKIP": "yellow", "FAIL": "red"}.get(label, "")
        table = Table.grid(padding=0)
        table.add_column(width=7, min_width=7, max_width=7, no_wrap=True)
        table.add_column(overflow="fold")
        table.add_row(Text(label, style=f"bold {colour}".strip()), Text(value))
        if detail:
            text = Text(detail, style="dim")
            text.stylize("bold", 0, detail.find(":") if ":" in detail else len(detail))
            table.add_row("", text)
        self.console.print(table)

    def scan(self, source: Path, root: Path):
        result = {"input": self.path(source), "root": self.path(root), "status": "scanning", "diagnostics": []}
        self.sources.append(result)
        return _ScanOutput(self, result)

    def skipped(self, source: Path, reason: str) -> None:
        self.sources.append({"input": self.path(source), "status": "skipped", "reason": reason})
        self.row("SKIP", self.path(source), reason)

    def saved(self, manifest: Path, metadata: dict[str, Any]) -> None:
        count = len(metadata.get("recordSet", []))
        self.sources[-1].update(status="added", manifest=self.path(manifest), record_sets=count)
        self.row("Saved", f"{self.path(manifest)} ({count} record {'set' if count == 1 else 'sets'})")

    def template(self, source: Path, path: Path) -> None:
        for result in self.sources:
            if result["input"] == self.path(source):
                result["annotation_template"] = self.path(path)
        self.row("Review", self.path(path))

    def warning(self, source: Path, message: str) -> None:
        for result in self.sources:
            if result["input"] == self.path(source):
                result.setdefault("diagnostics", []).append(
                    {"level": "warning", "logger": "biotope", "message": message}
                )
        self.row("WARN", self.path(source), message)


class _ScanOutput(logging.Handler):
    """Show upstream warnings live; publish confirmed file outcomes after assembly."""

    def __init__(self, output: AddOutput, result: dict[str, Any]) -> None:
        super().__init__(logging.WARNING)
        self.output = output
        self.result = result
        self.generator = None
        self.entries: dict[str, Any] = {}
        self.shown: set[tuple[str, ...]] = set()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.fields[count]}"),
            console=output.console,
            transient=True,
            disable=output.as_json or not output.console.is_terminal,
        )
        self.task = self.progress.add_task("Baking", total=None, count="")

    def __enter__(self):
        self.output.row("Source", self.result["root"] + "/")
        logging.getLogger("croissant_baker").addHandler(self)
        if not self.output.as_json and self.output.console.is_terminal:
            self.progress.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        if not self.output.as_json and self.output.console.is_terminal:
            self.progress.stop()
        logging.getLogger("croissant_baker").removeHandler(self)
        if exc is not None:
            self.result.update(status="failed", error=str(exc))
        if not self.output.as_json and "scan" in self.result:
            report = self.result["scan"]
            counts = [f"{report['total']} scanned", f"{report['described']} described"]
            counts.extend(f"{report[key]} {key}" for key in ("linked", "referenced") if report.get(key))
            if report["undescribed"]:
                counts.append(f"{report['undescribed']} not described")
            if self.result["diagnostics"]:
                count = len(self.result["diagnostics"])
                counts.append(f"{count} {'diagnostic' if count == 1 else 'diagnostics'}")
            self.output.console.print()
            self.output.row("Total", " · ".join(counts))

    def __call__(self, done: int, total: int, path: str) -> None:
        # Extraction is not yet a confirmed description. Assembly can still fail.
        self.progress.update(self.task, completed=done, total=total, count=f"{done}/{total}")
        if self.generator is not None and not self.output.as_json:
            if not self.entries:
                self.entries = {str(e.path): e for e in self.generator.scan_report.entries}
            entry = self.entries.get(path)
            if entry is not None and entry.outcome.value == "failed":
                self.file(
                    {
                        "path": path,
                        "outcome": "failed",
                        "reason": entry.reason.value,
                        "detail": entry.detail,
                    }
                )
        if done == total:
            self.progress.reset(self.task, description="Assembling", total=None, count="")

    def attach(self, generator: Any) -> None:
        """Observe public scan entries for failures that occur before assembly."""
        self.generator = generator

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        self.result["diagnostics"].append(
            {"level": record.levelname.lower(), "logger": record.name, "message": message}
        )
        # Baker logs have no stable source IDs; preserve them rather than guessing attribution.
        self.output.row("FAIL" if record.levelno >= logging.ERROR else "WARN", message)

    def finish(self, report: dict[str, Any]) -> None:
        self.result.update(scan=report, status="scanned")
        if self.output.as_json:
            return
        files = report["files"]
        groups = Counter(
            str(Path(f["path"]).parent)
            for f in files
            if f["outcome"] == "described" and Path(f["path"]).match("part-*.parquet")
        )
        shown = set()
        for file in sorted(files, key=lambda f: f["path"]):
            path = Path(file["path"])
            parent = str(path.parent)
            if file["outcome"] == "described" and path.match("part-*.parquet") and groups[parent] > 1:
                if parent not in shown:
                    self.output.row("OK", f"{parent}/ ({groups[parent]} Parquet files)")
                    shown.add(parent)
                continue
            self.file(file)

    def file(self, file: dict[str, Any]) -> None:
        identity = tuple(file.get(k, "") for k in ("path", "outcome", "reason", "detail"))
        if identity in self.shown:
            return
        self.shown.add(identity)
        status = {"described": "OK", "linked": "LINK", "referenced": "REF", "failed": "FAIL"}.get(
            file["outcome"], "SKIP"
        )
        reason = file.get("reason", "").replace("_", " ").capitalize()
        reason = {"Extract failed": "Extraction failed", "Build failed": "Assembly failed"}.get(reason, reason)
        detail = file.get("detail", "")
        if detail == "no handler for file type":
            detail = ""
        explanation = f"{reason}: {detail}" if reason and detail else reason or detail
        if reason and detail.lower().startswith(reason.lower()):
            explanation = detail[0].upper() + detail[1:]
        if file.get("duplicate_of"):
            explanation = f"Linked to {file['duplicate_of']}"
        elif file.get("part_of"):
            explanation = f"Represented by {file['part_of']}"
        self.output.row(status, file["path"], explanation)
