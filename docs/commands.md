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
biotope source register .biotope/reviews/study.jsonld --name study --reason "Reviewed source structure"
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
```

Registration stores the effective curated description. `--replace` replaces an
existing description after reporting removed structure; it does not merge files.

Generation gives every top-level record set, and every file no record set reads, a
package under `graph/sources/<manifest>/` with a schema, a `SOURCE` registration and
a placeholder loader. It creates missing files only and never rewrites an existing
schema, registration or loader; on a conflict it writes nothing. It prints each
package's status (created, completed, current, drift, orphaned or conflict) and
records every contract revision in `.biotope/contracts/`. `--package` overrides the
manifest-derived root name; `--check` writes nothing and fails only when generation
would create or change a file. Removed sources leave orphan packages: exclude them,
then delete their directories.

Use `annotate` to edit descriptive metadata and `config` to maintain annotation
requirements. See [shared annotation policies](cluster-compliance.md) for local
and remote settings.

## Author and build

| Command                                                 | Behavior                                                                                |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `biotope graph scaffold`                                | Create `graph/` with empty registries and a pipeline to implement.                      |
| `biotope map --purpose ... --entity ... --relation ...` | Record research requirements.                                                           |
| `biotope map --show`                                    | Show the current purpose and requirements.                                              |
| `biotope graph check`                                   | Check the source inventory, drift, declarations, requirement bindings and Python types. |
| `biotope graph quality`                                 | Check and execute the pipeline, printing an assessment without export.                  |
| `biotope graph build`                                   | Check and execute, then replace `graph/build/` after a successful export.               |
| `biotope graph metagraph`                               | Write an offline topology viewer to `graph/metagraph.html`.                             |

Graph commands support `--json`; check, quality, build and metagraph also accept
`--graph <folder>`. Scaffold always creates `graph/` in the current directory and
refuses an existing path. It performs no initialization, baking or execution.

Check, quality and build discover the source packages statically, then load
`topology/__init__.py:TOPOLOGY` and `pipelines/build_graph.py:PIPELINE`, so
inventory findings are reported even when the pipeline cannot be imported. Check
does not invoke loaders or mappings. `build --out <dir>` builds elsewhere; a build
replaces a directory only when it recognizes every file in it. Metagraph imports
topology independently; `--out <html>` selects a different viewer path and
`--report <run.json>` adds matching-topology observations.

Quality and build each execute the declared scope once. Running both executes
twice. Warnings require interpretation; definition, execution and integrity
failures can fail an operation. See [typed projects](mapping.md)
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

For removed commands and options, see [migration](migration.md).
