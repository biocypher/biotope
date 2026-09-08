# Command reference

Biotope supports local data descriptions, purpose and target-schema capture,
mapping definitions, and structural validation. Use `biotope <command> --help`
for options. The workflow stops at mapping.

## Setup and tracking

- `init <name>` creates a project; `init .` initializes the current directory.
  `--no-git` keeps the metadata workflow usable without creating a repository.
- `add <path>...` describes local files or directories with croissant-baker,
  records provenance and stages manifests if the project owns a Git repository.
  `--rebake` regenerates directory descriptions; use `--force` for an individual file.
- `mv`, `rm` maintain tracked paths and metadata.
- `queue` shows coarse `raw`, `processed` and `mapped` states; `mark` changes
  them manually. These states do not certify source values or graph readiness.
- `check-data` compares tracked file checksums; large files require reading bytes.

## Purpose and mappings

- `map --purpose ... --entity ... --relation ...` records research intent and
  target schema slots. `--show` prints them; bare `map` opens the wizard.
- `map inspect <manifest>` lists declared record sets, fields and sources.
  `--json` emits structural metadata without value samples.
- `map scaffold <manifest>` writes an unresolved mapping with an inspection
  appendix. `--stdout` prints it instead.
- `map preview [<mapping>]` checks definitions and summarizes the target schema.
  Without a path it checks all project mappings. `--json` supports agent use.
  Errors or partially filled bindings return exit code 1. Transform arguments and
  their source-field references are checked; source values and transform execution
  are not. Empty stubs are inactive in the existing multi-mapping model;
  inspect the proposed schema and compare coverage with project intent.
- `map defer-relation <mapping> <relation>` defers a relation already present in
  that file; `undefer-relation` reverses it. For a gap with no binding yet, add
  `<relation>: {deferred: true}` under `relations:` in the mapping YAML.

`propose-mapping` remains an alias for `map scaffold`.

## Metadata and version control

- `annotate` scaffolds, applies and validates metadata annotations.
- `config` manages metadata validation and project configuration.
- `status` summarizes tracked metadata and any Git changes.
- `commit`, `log`, `push`, `pull` require a Git repository for metadata history
  and synchronization.

Source-value loading, downloading, discovery and text extraction are outside
this command surface. Graph execution commands are unavailable in this iteration.
