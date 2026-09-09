# Commands

Use `biotope <command> --help` for options. Run project commands from the project
root with the intended environment activated.

## Describe and curate

- `init . --no-prompt` initializes the current directory; a name creates a new
  subdirectory. `--no-git` supports a metadata project without a repository.
  It writes metadata configuration and purpose files; it creates no graph workspace
  or Python dependency project. Other directories are created when needed.
- `add <path>...` uses croissant-baker to describe local files or directories.
  Human output shows source-relative paths with aligned statuses and wrapped diagnostics.
  Warnings and extraction failures appear live above terminal progress; confirmed
  descriptions follow assembly. Successful Parquet parts are grouped by directory.
  Files linked to or represented by other inputs use `LINK` and `REF`.
  Directory `--rebake` and file `--force` refresh descriptions. Curated or annotated manifests
  stop before overwrite. `add <path> --bake-to review/fresh.jsonld` writes a new
  review description without updating managed metadata or tracking. Reconcile it
  before registering a replacement. Baking and checksums read source bytes.
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
- `map inspect <manifest>` shows full source paths and declared field types in
  wrapping blocks. Fields retain their order; nested fields form a tree. Record sets
  sharing source IDs share a source heading. Redundant generated descriptions are
  omitted; meaningful descriptions and parse notes remain visible. It reads metadata only.
- `map inspect <manifest> --json > inspection.json` writes one JSON document to stdout
  (`schema_version: 2`). `record_sets` and recursive `sub_fields` retain exact IDs,
  names, declared `data_type`, descriptions, array shape and field `source` descriptors.
  Each record set's `source_ids` refers to `@id` entries in `distribution`; unresolved
  references remain present. Paths keep their declared form. Missing IDs are `null`.
  Additional metadata, including field references, is retained in `attributes`;
  `context` preserves the dataset's JSON-LD context. `kind` is a best-effort normalized
  classification, not a value check. Load errors go to stderr with a nonzero exit
  and no JSON on stdout.
- `source register <authored.jsonld> --name <dataset> --reason <review>` registers
  effective curated metadata. `--replace` explicitly replaces an existing description.
- `source generate <manifest> --out graph/sources/study/schema.py` generates source
  dataclasses, `RECORDS` and the `SourceRow` type union without payloads. It creates
  missing sibling `SOURCE` registration and loader files, preserving existing ones.
  `--check` verifies contract freshness without writing. Use a separate source
  directory for each generated module.
- `annotate` and `config` maintain descriptive annotations and validation settings.

## Define and build

- `graph scaffold [--json]` creates `graph/` in the current directory with topology,
  source and mapping registrations, inactive typed examples, a pipeline entry point,
  path constants and `pyproject.toml` with `biotope[graph]`. Source generation stays
  separate; BioCypher output uses the existing `graph build` command.
  Scaffolding needs no prior init or bake and performs neither. Existing
  `graph/` paths, including symlinks, are refused without modification. JSON reports
  the absolute `path` and created `files` relative to it. The template leaves
  scientific decisions unfilled and cannot silently execute as a finished graph.
- `map --purpose ... --entity ... --relation ...` captures research requirements.
  `map --show` prints existing intent. Bare `map` shows help.
- Author topology, source-local loaders, mappings and pipeline registration in
  Python under `graph/`. Run from the project root; use imports starting with `graph.`
  or package-relative imports. See the [typed project guide](mapping.md) and [example](tutorial.md).
- `graph check graph.pipelines.build_graph:PIPELINE [--json]` checks definitions, source freshness,
  requirement bindings and Python types. No loaders or mappings are invoked.
  Warnings identify absent intent, missing purpose/requirements and registered
  `example:` concepts; a successful definition check is not scientific acceptance.
- `graph build graph.pipelines.build_graph:PIPELINE --out graph/build/<run>` checks, executes the selected
  project pipeline and writes BioCypher files, provenance and `run.json`.

YAML mappings, their wizard/scaffolds/preview, `propose-mapping`, automatic
alignment proposals and the legacy graph engine are retired. No automatic
migration is provided. Downloading, discovery, built-in source readers and text
extraction remain outside the package.

## Track and review

- `queue` and `mark` maintain coarse `raw`, `processed` and `mapped` states.
  `mapped` is set manually; these states do not certify graph completion or scientific validity.
- `check-data` explicitly verifies recorded file checksums; large files require
  reading bytes. Definition checks do not invoke it.
- `mv` and `rm` maintain tracked paths. `rm` can delete source data; use ordinary
  filesystem archival of build outputs for test cleanup.
- `status` summarizes metadata and local Git changes. `commit`, `log`, `push`
  and `pull` require a project Git repository. Metadata commands do not stage
  authored Python automatically; review and version that code with normal Git.
