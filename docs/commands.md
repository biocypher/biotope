# Command reference

Biotope supports local data descriptions, purpose and target-schema capture,
mapping definitions, and structural validation. Use `biotope <command> --help`
for options. The workflow stops at mapping.

## Setup and tracking

- `init <name>` creates a project; `init .` initializes the current directory.
- `add <path>...` describes local files or directories with croissant-baker,
  records provenance and stages manifests. `--rebake` regenerates directory descriptions; use `--force` for an individual file.
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
  Errors or partially filled bindings return exit code 1; values and transformations
  are not checked. Empty stubs are inactive in the existing multi-mapping model;
  inspect the proposed schema and compare coverage with project intent.
- `map defer-relation <mapping> <relation>` records an unsupported relation;
  `undefer-relation` reverses it.
- `propose-alignment` suggests equivalences between mapping definitions for
  semantic review. It does not verify identities against data values.

`propose-mapping` remains an alias for `map scaffold`.

## Metadata and version control

- `annotate` scaffolds, applies and validates metadata annotations.
- `config` manages metadata validation and project configuration.
- `status`, `commit`, `log`, `push`, `pull` provide Git-style metadata history
  and synchronization.

Source-value loading, downloading, discovery and text extraction are outside
this command surface. Graph execution commands are unavailable in this iteration.
