---
name: biotope-croissant
description: Build a knowledge graph from data files using biotope, the CLI for the BioCypher ecosystem (Croissant-described data → BioCypher graph, with git-like metadata version control). Use this whenever the task is to turn tables, CSVs, JSON, parquet, or mixed/unstructured sources into a queryable knowledge graph or graph database (Neo4j, DuckDB) — including ingesting a dataset into a graph, mapping fields to entities and relations, building a BioCypher project, connecting biomedical/biological data across sources, or grounding data against ontologies. Trigger on mentions of biotope, BioCypher, Croissant, knowledge graph / KG construction, graph ingestion, "turn this data into a graph", entity/relation mapping, or ontology-grounded data integration — even when the user names the goal (a graph) rather than the tool.
---

# biotope: build a knowledge graph from data

biotope is a CLI. Never import its Python modules, browse its source, or hand-edit `.biotope/`. Use commands, flags, `--help`, and error text only. If stuck, ask the user.

Project layout: `.biotope/` (manifests + config), `data/`, `mappings/` (one `*.mapping.yaml` per logical dataset). `build` streams all mappings and deduplicates nodes by id.

First of all, ensure biotope>=0.8.0 is installed.

```bash
uvx biotope init ...     # no install: runs the latest biotope in an ephemeral venv (best for init)
pipx install biotope     # isolated global install you can call as `biotope`
uv add biotope           # inside an existing uv project
```

Unreleased checkout: `uv pip install -e /path/to/biotope` (use venv or `--break-system-packages` in containers). Verify with `biotope --version`.

## Pipeline

```
init  →  add  →  map  →  build  →  verify
```

`biotope status` / `biotope queue` show pipeline state. In uv projects: `uv run biotope ...`.

## Agent loop — do not skip

Mapping is iterative. A clean `preview` does **not** mean edges resolve — orphans appear only after build.

```
inspect --json  →  write mapping  →  preview --json  →  build  →  view
       ↑___________________________________|  (fix mapping, not generated code)
```

**Before build** — run `biotope map preview --json` and parse the JSON (rich output truncates in agent context). Gate:

- `unresolved_slots` empty; `findings` has no errors
- Mapping covers every `required_entity` / `required_relation` from `project.yaml`
- Every relation **target** entity is emitted from **every** record set that references it (see `references/mapping.md`, shared entities)
- `sample_edge_tuples` target ids use the same id minting as the entity definition
- Binding still matches the user's stated `purpose` and entities — if not, **ask** (defer unsupported relations, or get explicit consent before changing the schema)

**After build** — `biotope view` and `build/biocypher-out/build_metrics.json`. `orphaned_count` must be 0. Non-zero → fix ids or entity coverage, re-preview, rebuild. Relation with far fewer edges than expected → id-namespace mismatch.

**When to ask the user:** purpose vs mapping mismatch; relation unsupported by data; disagreeing id columns across sources; need `--clear-entities` / `--clear-relations`.

### 1. Orient

Ask the user: what should this graph answer? What entities and relations matter? Answers become `purpose` and `biotope map --entity` / `--relation` flags. Don't infer from file shapes alone. If `project.yaml` already has intent, confirm it's current. Never silently overwrite it (`references/reliability.md`).

### 2. init — scaffold

Pure scaffolder: makes the directory layout, an empty `project.yaml`, and a starter `pyproject.toml`, then `git init`. No content questions. **Pick the target form deliberately** — this is where agents most often fumble:

```bash
# A) Create a NEW subfolder named my-kg under the current directory:
biotope init my-kg --purpose "What approved drugs target genes in T2D?" --no-prompt
cd my-kg && uv sync

# B) Initialise IN the folder you're already in (e.g. an existing repo/workspace):
biotope init . --no-prompt        # project root is the current directory
uv sync
```

Use `.` when the user wants biotope set up inside a folder that already exists; use a name when you're creating a fresh project directory. Don't probe by trial-and-error in `/tmp` — pick the form from the user's intent. **Form A always requires the `cd`** — every command in the rest of this pipeline (`queue`, `add`, `map`, `build`, ...) assumes the working directory is the project root, so running them from the parent directory after `init my-kg` will fail to find the project.

Containers may skip auto-commit (missing git identity) — harmless. **Never `--no-git`** in fresh/ephemeral environments; biotope needs `.biotope` + `.git` to find the project.

### 3. add — bring data under the project

A biotope project **owns its data**: files must live under the project root before they can be described (the manifest addresses paths relative to the project). Copy a local folder in, or fetch a URL with `biotope get`; symlinks out of the tree are rejected.

```bash
biotope get https://example.org/opentargets.parquet --output-dir data/ot --no-add
biotope add data/ot --license CC-BY-4.0 --creator "Open Targets" --description "..."
```

`biotope add <dir>` runs croissant-baker over the directory and writes **one** manifest at `.biotope/datasets/<rel>.jsonld` covering the whole subtree. Pass metadata the baker cannot infer (license, creator, description, access terms) as flags. **One logical dataset → one manifest** — point `add` at the folder that *is* the dataset, never at individual partition files, and don't split one dataset across subdirectory `add`s (it fragments lineage). For genuinely independent datasets under a shared parent, add each as its own path: `biotope add data/study_a data/study_b`.

Stale manifest after preprocessing → `biotope add <dir> --rebake`.

The **queue** tells you each dataset's state:

```bash
biotope queue          # human-readable; biotope queue --json for machines
```

- **raw** — baker couldn't structure the file (free-form text, PDF). It needs an extraction step before it can be mapped.
- **processed** — schema is concrete; ready to map.
- **mapped** — a resolved mapping exists.

For raw inputs, extract the schema-shaped facts into a structured file and record provenance — this is the one genuinely manual step (see `references/reliability.md`, "extraction is the manual step"):

```bash
biotope add data/notes/hubs.csv --derived-from data/notes/airports-notes.md
```

`--derived-from` stamps the lineage and drops the raw source from the active queue without moving it.

### 4. map — declare intent, then bind slots

`map` does two distinct things. First, **capture intent** non-interactively (always use flags as an agent; bare `biotope map` opens a human wizard):

```bash
biotope map --entity gene --entity disease --entity drug \
            --relation gene_associated_with_disease
```

This appends to `required_entities` / `required_relations` in `project.yaml`. Names accept free text and are normalised to `snake_case`. Adding is always safe; `--clear-entities` / `--clear-relations` are destructive and need the user's explicit say-so.

Second, **author mapping YAML** per dataset. Read `references/mapping.md` first. Follow the [agent loop](#agent-loop--do-not-skip):

```bash
biotope map scaffold .biotope/datasets/data/ot.jsonld
biotope map inspect  .biotope/datasets/data/ot.jsonld --json
# edit mappings/ot.mapping.yaml
biotope map preview --json
```

Cross-file identity = matching ids (same field semantics, transform, prefix). `biotope propose-alignment mappings/*.mapping.yaml` proposes only — audit each (`references/reliability.md`).

### 5. build — choose the output target, materialise, then run

**Decide the output format with the user first** — don't default silently. `biotope build --target {csv,neo4j}` (default `csv`). See `references/output-targets.md` for what biotope covers vs optional downstream steps.

```bash
biotope build --target neo4j        # strict: refuses any unresolved slot
uv run python build/create_knowledge_graph.py
```

`build` writes plain, committable Python + YAML under `build/` (`config/schema_config.yaml`, an adapter per mapping, and `create_knowledge_graph.py`) and prints the resolved `target (dbms)`. The entry point regenerates `build/biocypher-out/` from scratch each run (so re-running after a target change is clean) and writes `build_metrics.json` (orphaned edges + compile drops).

### 6. Verify

```bash
biotope view      # counts, orphaned edges, schema diff
biotope status
```

See [agent loop](#agent-loop--do-not-skip). Never claim success without `biotope view` showing non-empty output and stating the reported target.

## Reliability

`references/reliability.md` — canonical ids, edge survival, honest schema, audited alignments. Read on non-trivial graphs.

## House rules

- Flags only, no interactive prompts. Wrong output → fix purpose/mapping/data, re-run. Only editable generated file: `build/config/biocypher_config.yaml`.
- Metadata moves via `biotope add` / `commit` / `mv`, not raw file moves.
- Keep `purpose:` honest.

## Command reference

```
init                              project scaffolding
get add mv rm                     acquisition + tracking (baker writes croissants)
queue mark                        pipeline-state dashboard + manual transitions
map (inspect|scaffold|preview)    semantic mapping (intent + wizard + agent path)
propose-alignment                 cross-mapping same_node equivalences
build view                        build + inspect a graph
status commit log push pull       git-like metadata version control
check-data                        checksum verification
annotate config                   field-level annotation + project config
discover                          find candidate datasets for declared entities
```

## Optional next steps

Ask before Neo4j import, BioCypher tuning, or NL querying. CSV-only may be the end state.

- Neo4j / BioCypher outputs → **biocypher** skill
- NL querying → **biochatter** skill (needs loaded graph + `schema_info.yaml`)
