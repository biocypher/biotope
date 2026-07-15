# Commands

`biotope --help` lists command groups. Run `biotope <command> --help` for
current flags and examples. This page shows how commands fit into the pipeline.

## Project lifecycle

- `biotope init`: scaffold a project (`.biotope/`, `project.yaml`, `git init`).

## Data acquisition and tracking

- `biotope get <url>`: download a file, optionally into `--output-dir`, and
  track it unless you pass `--no-add`.
- `biotope add <path>`: stage data files or rooted directories. Baker writes
  Croissant metadata under `.biotope/datasets/`. `--derived-from` records
  provenance for extracted files. For metadata that does not fit in CLI flags,
  such as citations or per-record-set fields, `add` also writes a
  `.biotope.yaml` scaffold next to the dataset. Review it, then run
  `biotope annotate apply <dir>` to merge it into the manifest.
- `biotope mv` / `biotope rm`: move or untrack files and update metadata paths.
- `biotope queue`: group every dataset by pipeline state (`raw`, `processed`,
  or `mapped`). Use it as the dashboard during a build.
- `biotope mark <dataset> <status>`: set a dataset's `biotope:status` manually.

## Semantic mapping

For the mapping YAML grammar and reliability rules, see the
[mapping reference](mapping.md).

- `biotope map`: update `project.yaml` non-interactively when passed intent
  flags (`--purpose`, `--entity`, `--relation`, `--source`, `--notes`,
  `--clear-*`, or `--show`). With no flags, it opens the guided wizard.
- `biotope map inspect <croissant>`: list fields and sample rows. Pass `--json`
  for machine-readable output.
- `biotope map scaffold <croissant>`: write an unresolved mapping scaffold
  with the inspection results in a comment appendix.
- `biotope map preview [<mapping>]`: validate a partial mapping and show its
  projected BioCypher schema and sample tuples. Pass `--json` for agents.
- `biotope propose-alignment`: propose cross-mapping `same_node` equivalences.

## Git-like metadata VCS

- `biotope status`: show staged or modified files and validation state.
- `biotope commit`: commit metadata changes.
- `biotope log`: show metadata commit history.
- `biotope push` / `biotope pull`: sync metadata with a remote.
- `biotope check-data`: verify data files against recorded checksums.

## Knowledge-graph construction

- `biotope build`: create a runnable BioCypher project from mappings and
  alignment. It writes `config/schema_config.yaml` and generated Python for
  each mapping under `build/generated/<stem>/`.
- `biotope view`: show node and edge counts for the latest build, or project
  competence questions before the first build.

## Annotation and project configuration

- `biotope annotate`: apply or edit metadata, load sample records, and validate
  manifests. `apply` accepts `--set dataset.<field>=...` and
  `--set record_set.<field>=...` overrides.
- `biotope config`: manage validation rules, remote validation URLs, and
  project metadata.

## Not yet implemented

- `biotope discover`: rank registered adapters and local Croissant files
  against `required_entities`. The registry is not part of the recommended
  workflow yet.
- `biotope benchmark`: emit a skeleton metrics object for downstream tests.
  Quality and coverage metrics are not implemented yet.
- `biotope read`: reserved for NLP ingestion. It currently provides a health
  check only.
- `biotope search`: search MCP and bio.tools registries. The standard build
  path does not use it.

## Deprecated

- `biotope describe`: removed. Use the intent flags on `biotope map`.
- `biotope propose-mapping`: deprecated alias for `biotope map scaffold`. It
  writes an unresolved scaffold for a human or agent to complete.
