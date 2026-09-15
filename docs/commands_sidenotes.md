# CLI report formats

These notes accompany the [command reference](commands.md). JSON reports are
useful for scripts and for reviewing scan coverage without terminal formatting.

## Source reports

- `add <path>... --json` writes one JSON report to stdout; human output and upstream
  logs stay on stderr, with no progress animation. For example:
  `biotope add raw --json > scan.json` (keep the report outside the scanned directory).
  The report contains `schema_version`, `project_root`, overall `status`, and `sources`.
  Each scanned source includes `input`, `root`, the full Baker `scan` report with
  per-file outcomes/reasons/details, captured log `diagnostics`, and written artifact paths.
  Paths are relative to `project_root`; paths inside `scan.files` are relative to the source's `root`.
  JSON keeps every file even when human output groups partitions. Partial-parse warnings
  remain diagnostics; a `described` outcome does not certify completeness.
  `complete_with_gaps` means metadata was written with undescribed files or diagnostics.
  Already tracked inputs are `skipped`; a wholly skipped run is `unchanged`.
  Runtime failures produce `status: failed` and a nonzero exit. Argument-parsing errors
  use Click's ordinary stderr errors before a report is started.
- `map inspect <manifest> --json > inspection.json` writes one JSON document to stdout
  (`schema_version: 2`). `record_sets` and recursive `sub_fields` retain exact IDs,
  names, declared `data_type`, descriptions, array shape and field `source` descriptors.
  Each record set's `source_ids` refers to `@id` entries in `distribution`; unresolved
  references remain present. Paths keep their declared form. Missing IDs are `null`.
  Additional metadata, including field references, is retained in `attributes`;
  `context` preserves the dataset's JSON-LD context. `kind` is a best-effort normalized
  classification, not a value check. Load errors go to stderr with a nonzero exit
  and no JSON on stdout.

## Graph reports

Graph commands accept `--json` and emit one document with `schema_version: 1`
and an operation-specific `report_kind`. Diagnostics and incidental project
output go to stderr. Operational failures also produce a report; argument errors
can occur before reporting starts and use the CLI's normal stderr output.

Quality saves its latest assessment in `<graph>/reports/quality.json`, including
failed assessments. Build includes the assessment in `<run>/run.json`. Metagraph
JSON writes no HTML and cannot be combined with `--out`.

See [typed graph technical notes](mapping_sidenotes.md) for measurement limits,
provenance and export artifacts.
