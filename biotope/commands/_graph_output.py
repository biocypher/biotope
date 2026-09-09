"""Human graph reports and JSON isolation; no graph execution or data reading."""

from __future__ import annotations

import json
import os
import sys
from contextlib import redirect_stdout
from typing import Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from biotope.graph.reports import Finding


class GraphOutput:
    def __init__(self, operation: str, target: str, as_json: bool, *, console: Console | None = None):
        self.operation, self.target, self.as_json = operation, target, as_json
        self.console = console or Console(stderr=True)
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            console=self.console,
            transient=True,
            disable=as_json or not self.console.is_terminal,
        )
        self.seen: set[str] = set()
        self.task = self.progress.add_task("Loading definitions", total=None)

    def __enter__(self) -> GraphOutput:
        # Redirect both Python streams and native/subprocess writes while project code runs.
        sys.stdout.flush()
        self.stdout_fd = os.dup(1)
        os.dup2(2, 1)
        self.redirect = redirect_stdout(sys.stderr)
        self.redirect.__enter__()
        if not self.as_json:
            self.row(self.operation.capitalize(), self.target)
            if self.operation in ("quality", "build"):
                self.row(
                    "Scope",
                    "Run loaders and mappings; " + ("no export" if self.operation == "quality" else "then export"),
                )
            self.progress.start()
        return self

    def __exit__(self, *args: Any) -> None:
        try:
            self.progress.stop()
            sys.stdout.flush()
        finally:
            self.redirect.__exit__(*args)
            os.dup2(self.stdout_fd, 1)
            os.close(self.stdout_fd)

    def phase(self, name: str) -> None:
        self.progress.update(self.task, description=name.capitalize())

    def row(self, status: str, subject: str, detail: str = "") -> None:
        table = Table.grid(padding=0)
        table.add_column(width=10, no_wrap=True)
        table.add_column(overflow="fold")
        color = {"OK": "green", "WARN": "yellow", "FAIL": "red", "SKIP": "yellow"}.get(status, "")
        table.add_row(Text(status, style=color), Text(subject))
        if detail:
            table.add_row("", Text(detail))
        self.console.print(table)

    def on_finding(self, finding: Finding) -> None:
        self.finding(finding.to_json())

    def finding(self, finding: dict[str, Any]) -> None:
        key = json.dumps(finding, sort_keys=True)
        if self.as_json or key in self.seen:
            return
        self.seen.add(key)
        # Existing project exclusions have their own compact representation.
        if finding.get("kind") == "exclusion":
            self.row("INFO", f"Excluded {finding['count']}: {finding['policy']}")
            return
        label = {"error": "FAIL", "warning": "WARN", "info": "INFO"}.get(finding["severity"], "INFO")
        location = finding.get("location")
        detail = finding["message"]
        if location:
            path = location["path"]
            if location.get("line") is not None:
                path += f":{location['line']}"
                if location.get("column") is not None:
                    path += f":{location['column']}"
            detail = path + "\n" + detail if path != finding["subject"] else detail
        self.row(label, finding["subject"], detail)

    def finish(self, report: dict[str, Any]) -> None:
        if self.as_json:
            click.echo(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
            return
        definitions = report.get("definitions") or (
            report if report.get("report_kind") == "biotope.definitions" else {}
        )
        checks = definitions.get("checks", [])
        passed = [c["name"] for c in checks if c["state"] == "passed"]
        if passed:
            self.row("OK", " · ".join(passed))
        for check in checks:
            if check["state"] == "skipped":
                self.row("SKIP", check["name"], check["reason"])
        findings = [*definitions.get("findings", []), *report.get("quality", {}).get("findings", [])]
        if definitions is not report:
            findings.extend(report.get("findings", []))
        for finding in findings:
            self.finding(finding)
        for key, reason in definitions.get("deferrals", {}).items():
            self.row("Defer", key, reason)
        measurements = report.get("quality", {}).get("measurements", {})
        if measurements:
            self.quality(measurements)
        if report.get("quality", {}).get("state") == "not_run":
            self.row("SKIP", "Quality measurements", report["quality"]["reason"])
        if self.operation == "scaffold" and report.get("state") == "complete":
            self.row("Created", f"{len(report['files'])} files in {report['path']}")
        for key in ("report_path", "html_path"):
            if report.get(key):
                self.row("Saved", report[key])
        self.row("FAIL" if report.get("state") == "failed" else "Done", report.get("state", "complete"))

    def quality(self, measurements: dict[str, Any]) -> None:
        for name, value in measurements.items():
            if name == "population":
                self.row("Counts", " · ".join(f"{k}: {v}" for k, v in value.items()))
            elif name == "properties":
                for concept, properties in value.items():
                    for prop, stats in properties.items():
                        if (
                            stats["total"]
                            and any(stats[k] for k in ("null", "blank", "empty_list"))
                            and stats["missing"] != stats["total"]
                        ):
                            self.row(
                                "Missing",
                                f"{concept}.{prop}",
                                f"{stats['total']} records · {stats['null']} null · "
                                f"{stats['blank']} blank · {stats['empty_list']} empty list",
                            )
            elif name == "connectivity":
                share = f"{value['largest_share']:.1%}" if value["largest_share"] is not None else "unmeasured"
                self.row("Connect", f"{value['components']} components · largest: {share}")
                sizes = ", ".join(f"{size} nodes × {count}" for size, count in value["size_distribution"].items())
                self.row("Sizes", sizes or "No nodes")
                self.row(
                    "Isolated",
                    f"{value['isolated_total']} nodes",
                    " · ".join(f"{k}: {v}" for k, v in value["isolated_by_type"].items()),
                )
            elif name == "concentration":
                for relation, sides in value.items():
                    for side, stats in sides.items():
                        if stats["total"]:
                            top = "; ".join(f"{r['id']}: {r['count']}/{stats['total']}" for r in stats["top"])
                            self.row("Degrees", f"{relation} · {side}", f"{stats['distinct']} IDs · {top}")
            elif name == "self_loops":
                self.row(
                    "Loops", " · ".join(f"{k}: {v['count']}/{v['total']}" for k, v in value.items()) or "No relations"
                )
            else:
                # New diagnostics remain visible without coupling their algorithm to this renderer.
                self.row("Measure", name, json.dumps(value, ensure_ascii=False))
