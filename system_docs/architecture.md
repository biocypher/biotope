# Architecture

Biotope keeps three things apart: describing sources, the project's graph code, and running that code. Croissant manifests record what is known about each source. The project's Python code, in its `graph/` workspace, defines how selected records become graph objects. Biotope checks that code, runs it and exports the result.

## Data flow

```text
local data ── croissant-baker ── manifest ◄── annotation file
    │                               │
    │                    source generate: one package per table or file
    │                               │
documents ── project extractors ── records file (registered as a dataset)
                                    │
           project loaders ── typed records ── alignment ── mappings
                                                               │
                                       checked graph objects ── export: Neo4j import files or SQLite
```

## Modules

| Module | Responsibility |
| --- | --- |
| `biotope.cli`, `biotope.commands` | The CLI. Each command orchestrates; `_add_output.py` and `_graph_output.py` render reports |
| `biotope.croissant` | Croissant models, manifest inspection, annotation files (`annotation.py`) and path IDs (`ids.py`) |
| `biotope.metadata`, `biotope.project_model`, `biotope.utils` | Manifest merging and status, the project's purpose file, project root and git-ignore checks |
| `biotope.extraction` | The extraction contract (`Extraction`, `Extractor`, `Document`), schema parsing, the runner and the records dataset |
| `biotope.graph` | Source generation and inventory, typed contracts, checks, the runtime, quality, export and the metagraph viewer |
| `biotope.templates` | The `graph/` scaffold and the source package templates |
| croissant-baker | Describing local files: formats, tables, fields, checksums |
| BioCypher | Writing the Neo4j import files |

Inside `biotope.graph`:

- Sources: `targets.py` lists what a manifest describes. `inventory.py` plans and writes packages, `render.py` renders them, `survey.py` reads them back and reports inventory findings, `revisions.py` formats revisions and current contracts for drift findings, and `moves.py` rewrites IDs for `biotope mv`.
- Checks: `workspace.py` imports the workspace, `check.py` runs the definition checks and Pyright, `signatures.py` checks mapping signatures, `topology.py` checks the topology, `standardization.py` checks terms and field bindings, and `dependencies.py` compares imports with `graph/pyproject.toml`.
- Execution and output: `runtime.py` holds `RunContext`, `build.py` runs a pipeline, `quality.py` measures the result, `provenance.py` collects evidence, `output.py` writes BioCypher or SQLite output, and `reports.py` and `artifacts.py` hold reports and build folders.

## Execution boundaries

- `biotope graph check` reads the source packages statically, imports declarations and runs Pyright. It does not run loaders, mappings or extractors.
- Project modules hold declarations only at import. Data access and work happen inside functions that Biotope calls. This is a contract for authors, not a sandbox: Biotope imports and runs project code.
- `graph quality` and `graph build` each run the pipeline once. A build stages its output in `graph/.build-*/` and replaces `graph/build/` only after success. A failed rebuild keeps the previous build and writes `graph/build/last_failure.json`.
- The whole graph, with its evidence, is held in memory. Streaming loaders do not change that.
- `graph metagraph` imports only the topology.
- Only `extract try` and `extract run` call an extractor. Checks and builds do not.

## Invariants

Tests guard each of these. Read the named tests before changing the behavior.

- An ID depends only on the path of a file or table within its dataset, not on listing order, other files, content or the machine (`tests/croissant/test_stable_ids.py`).
- A failed `biotope mv` changes nothing (`tests/commands/test_mv.py`).
- A rebake succeeds and keeps every annotation. Commands write into an annotation file only the values they are given (`tests/commands/test_refresh.py`).
- Generation does not rewrite an authored file. Only `biotope mv` changes the IDs in a schema (`tests/graph/test_source_generation.py`).
- A source revision covers structure: fields, types, nullability, keys, array shapes and file references. Descriptions, checksums and sizes do not change it (`tests/graph/test_source_revisions.py`).
- Biotope does not write to git, and writes only in its own places (`tests/commands/test_project_places.py`).
- Biotope writes a creator or license only when someone gave it.

## The extraction runner

- The records file's description lists under `isBasedOn` each document the extraction read, with the checksum it had, and names the run's schema revision and extractor. A document that failed has no checksum. Each stored record also carries its document's checksum, schema revision and extractor. The next run compares both with the current ones to decide what to extract again, so a document that gave no records is reused too.
- `source generate` and `graph check` read `isBasedOn` without importing project code, so these documents get no package.
- A document is extracted again only when its checksum, the schema revision, or the extractor's name, version or settings change, or when `--redo` names it.
- Biotope creates the extractor once per run, and only when a document needs extraction, so a run that reuses every record needs no API key.
- Each finished document's records go to `.biotope/progress/` at once. The records file and its description are written only when the run completes, so an interrupted run changes neither, and the next run reuses what it finished.
- A record's ID is its dataset's name, the document's path within the dataset and its key values. Moving a whole dataset folder therefore keeps the IDs.
