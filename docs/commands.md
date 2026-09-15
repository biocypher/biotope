# Commands

Run project commands from the project root with its environment activated. Use
`biotope <command> --help` for options. With a uv-managed environment, prefix
commands with `uv run`.

## Initialize and describe

| Command                          | Purpose                                                                                     |
| -------------------------------- | ------------------------------------------------------------------------------------------- |
| `biotope init my-kg`             | Create a metadata project in a new subdirectory.                                            |
| `biotope init . --no-prompt`     | Initialize the current directory using defaults; add `--no-git` to skip Git initialization. |
| `biotope add <path>...`          | Describe local files or directories with croissant-baker.                                   |
| `biotope add <path> --json`      | Emit per-file scan outcomes and diagnostics as JSON.                                        |
| `biotope map inspect <manifest>` | Inspect record sets and declared field types without reading payloads.                      |

Initialization writes metadata configuration and purpose files. It does not create
a graph workspace or install Python dependencies. Baking and checksum verification
read source bytes; metadata inspection does not.

`add --rebake` refreshes a directory description and `add --force` refreshes a file
description. Curated or annotated manifests are protected from overwrite. Use
`add <path> --bake-to <new-review.jsonld>` to bake separately for reconciliation.
Keep that output outside the input directory and `.biotope/datasets/`.

## Curate and generate

```bash
biotope source register graph/metadata/study.jsonld --name study --reason "Reviewed source structure"
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
```

Registration stores the effective curated description. `--replace` replaces an
existing description after reporting removed structure; it does not merge files.

Generation creates one package per top-level record set. Existing authored loaders
and registrations are preserved. `--package` overrides the manifest-derived folder
name; `--check` reports freshness without writing. Removed record sets leave
reported orphan packages for the project to review.

Use `annotate` to edit descriptive metadata and `config` to maintain annotation
requirements. See [shared annotation policies](cluster-compliance.md) for local
and remote settings.

## Author and build

| Command                                                 | Behavior                                                                               |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `biotope graph scaffold`                                | Create `graph/` with inactive examples and a pipeline to implement.                    |
| `biotope map --purpose ... --entity ... --relation ...` | Record research requirements.                                                          |
| `biotope map --show`                                    | Show the current purpose and requirements.                                             |
| `biotope graph check`                                   | Check declarations, generated source freshness, requirement bindings and Python types. |
| `biotope graph quality`                                 | Check and execute the pipeline, saving an assessment without export.                   |
| `biotope graph build --out graph/build/review-1`        | Check and execute, then export to a new run directory.                                 |
| `biotope graph metagraph`                               | Write an offline topology viewer to `graph/reports/metagraph.html`.                    |

Graph commands support `--json`; check, quality, build and metagraph also accept
`--graph <folder>`. Scaffold always creates `graph/` in the current directory and
refuses an existing path. It performs no initialization, baking or execution.

Check, quality and build load `topology/__init__.py:TOPOLOGY` and
`pipelines/build_graph.py:PIPELINE`. Check does not invoke loaders or mappings.
Metagraph imports topology independently; `--out <html>` selects a different viewer
path and `--report <quality.json-or-run.json>` adds matching-topology observations.

Quality and build each execute the declared scope once. Running both executes
twice. Warnings require interpretation; definition, execution, integrity and
declared validation failures can fail an operation. See [typed projects](mapping.md)
for authoring and [report formats](commands_sidenotes.md) for JSON details.

## Track and review

| Command                                 | Purpose                                                             |
| --------------------------------------- | ------------------------------------------------------------------- |
| `biotope queue`, `biotope mark`         | Inspect and maintain coarse `raw`, `processed` and `mapped` states. |
| `biotope check-data`                    | Read source bytes to verify recorded checksums.                     |
| `biotope mv`, `biotope rm`              | Maintain tracked paths; `rm` can delete source data.                |
| `biotope status --detailed`             | Review metadata, annotation issues and local Git changes.           |
| `biotope commit`, `log`, `push`, `pull` | Work with the project's Git repository.                             |

Queue states do not certify graph validity. Metadata commands do not automatically
stage authored Python; version that code with normal Git. Build outputs can be
archived separately without changing tracked source data.

For commands removed in 0.9, see [migration](migration.md).
