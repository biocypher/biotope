---
name: biotope
description: >-
  Build a knowledge graph from data files using biotope, the CLI for the
  BioCypher ecosystem (Croissant-described data → BioCypher graph, with
  git-like metadata version control). Use this whenever the task is to turn
  tables, CSVs, JSON, parquet, or mixed/unstructured sources into a queryable
  knowledge graph or graph database (Neo4j, DuckDB) — including ingesting a
  dataset into a graph, mapping fields to entities and relations, building a
  BioCypher project, connecting biomedical/biological data across sources, or
  grounding data against ontologies. Trigger on mentions of biotope, BioCypher,
  Croissant, knowledge graph / KG construction, graph ingestion, "turn this
  data into a graph", entity/relation mapping, or ontology-grounded data
  integration — even when the user names the goal (a graph) rather than the
  tool.
---

# biotope: build a knowledge graph from data

biotope is a CLI. The whole contract is the CLI — never import biotope's Python
modules and never hand-edit the files under `.biotope/`; every action is a
command or a flag. Your job is the semantic judgement (which record set is an
entity, which field is its id, which transforms apply); biotope enumerates
options, validates, and builds deterministically.

A project is a directory with `.biotope/` (manifests + config), `data/` (the
files), and `mappings/` (one `*.mapping.yaml` per logical dataset). Real
projects hold **several** mappings; `build` streams nodes and edges from all of
them and deduplicates nodes by id at build time.

## The pipeline

```
init  →  add  →  map  →  build  →  run + verify
```

Run `biotope status` / `biotope queue` any time to see where things stand. In a
uv-managed project prefix commands with `uv run` (`uv run biotope ...`); with a
global install just call `biotope`.

### 0. Get biotope on the PATH

Prefer an isolated, current install — **don't** `pip install --break-system-packages`
into the system Python (it tends to resolve a stale version and pollutes the
environment):

```bash
uvx biotope init ...     # no install: runs the latest biotope in an ephemeral venv (best for init)
pipx install biotope     # isolated global install you can call as `biotope`
uv add biotope           # inside an existing uv project
```

After `init`, the project gets its own `pyproject.toml`; from then on run
commands through the project venv (`uv sync` once, then `uv run biotope ...`).
If `biotope --version` looks old, you're on a stale global copy — reinstall with
one of the above rather than working around it.

### 1. Orient before touching anything

Elicit, in the user's own words, the questions the graph must answer, the
**entities** (the nouns of their domain), the **relations** between them, and
which datasets they already have versus need to find. Some of this may already
be in `.biotope/project.yaml` (`purpose`, `required_entities`,
`required_relations`) — confirm it's current rather than assuming, and never
silently overwrite it (see the schema-is-a-contract rule in
`references/reliability.md`).

### 2. init — scaffold

Pure scaffolder: makes the directory layout, an empty `project.yaml`, and a
starter `pyproject.toml`, then `git init`. No content questions. **Pick the
target form deliberately** — this is where agents most often fumble:

```bash
# A) Create a NEW subfolder named my-kg under the current directory:
biotope init my-kg --purpose "What approved drugs target genes in T2D?" --no-prompt
cd my-kg && uv sync

# B) Initialise IN the folder you're already in (e.g. an existing repo/workspace):
biotope init . --no-prompt        # project root is the current directory
uv sync
```

Use `.` when the user wants biotope set up inside a folder that already exists;
use a name when you're creating a fresh project directory. Don't probe by
trial-and-error in `/tmp` — pick the form from the user's intent.

**Fresh environments (containers/CI) often have no git identity**, so init's
auto-commit step prints `unable to auto-detect email address` and leaves the
scaffold staged. That's harmless — the project is fully initialised. Either set
identity once (`git config user.email you@example.com && git config user.name
you`) or pass `--no-git` to skip git entirely.

### 3. add — bring data under the project

A biotope project **owns its data**: files must live under the project root
before they can be described (the manifest addresses paths relative to the
project). Copy a local folder in, or fetch a URL with `biotope get`; symlinks
out of the tree are rejected.

```bash
biotope get https://example.org/opentargets.parquet --output-dir data/ot --no-add
biotope add data/ot --license CC-BY-4.0 --creator "Open Targets" --description "..."
```

`biotope add <dir>` runs croissant-baker over the directory and writes **one**
manifest at `.biotope/datasets/<rel>.jsonld` covering the whole subtree. Pass
metadata the baker cannot infer (license, creator, description, access terms) as
flags. **One logical dataset → one manifest** — point `add` at the folder that
*is* the dataset, never at individual partition files, and don't split one
dataset across subdirectory `add`s (it fragments lineage). For genuinely
independent datasets under a shared parent, add each as its own path:
`biotope add data/study_a data/study_b`.

If you edit the files in an already-tracked directory (e.g. preprocessing adds a
column), the manifest goes stale — `map` warns when it detects drift. Refresh it
with `biotope add <dir> --rebake`; biotope refuses to silently re-bake a tracked
directory, so a new column isn't mappable until you do.

The **queue** tells you each dataset's state:

```bash
biotope queue          # human-readable; biotope queue --json for machines
```

- **raw** — baker couldn't structure the file (free-form text, PDF). It needs an
  extraction step before it can be mapped.
- **processed** — schema is concrete; ready to map.
- **mapped** — a resolved mapping exists.

For raw inputs, extract the schema-shaped facts into a structured file and
record provenance — this is the one genuinely manual step (see
`references/reliability.md`, "extraction is the manual step"):

```bash
biotope add data/notes/hubs.csv --derived-from data/notes/airports-notes.md
```

`--derived-from` stamps the lineage and drops the raw source from the active
queue without moving it.

### 4. map — declare intent, then bind slots

`map` does two distinct things. First, **capture intent** non-interactively
(always use flags as an agent; bare `biotope map` opens a human wizard):

```bash
biotope map --entity gene --entity disease --entity drug \
            --relation gene_associated_with_disease
```

This appends to `required_entities` / `required_relations` in `project.yaml`.
Names accept free text and are normalised to `snake_case`. Adding is always
safe; `--clear-entities` / `--clear-relations` are destructive and need the
user's explicit say-so.

Second, **author one mapping file per dataset** that resolves those slots
against real fields. Scaffold an empty mapping (its comment appendix lists every
record set, field, id-like candidate, and sample rows), inspect when you need
more, edit the YAML, then preview:

```bash
biotope map scaffold .biotope/datasets/data/ot.jsonld
biotope map inspect  .biotope/datasets/data/ot.jsonld --json   # field catalogue
# edit mappings/ot.mapping.yaml
biotope map preview --json                                     # validate ALL mappings
```

The mapping YAML grammar — id selectors, transforms, `scan: row` vs
`explode`, multi-axis scans, relation endpoints, reusable `ids:`/`use:` — is in
`references/mapping.md`. Read it before writing a mapping. Iterate `preview`
until `unresolved_slots` is empty and `findings` has no errors. `inspect` and
`preview` are the canonical evidence views — never run `build` hoping for an
error message to tell you the schema.

Cross-mapping identity (the same node arriving from two files) is handled by
matching ids, not by a merge step — if both sides mint the id the same way,
BioCypher dedups them. `biotope propose-alignment mappings/*.mapping.yaml` only
proposes equivalences and only across ≥2 files; **audit every proposal, apply
none blind** (see `references/reliability.md`).

### 5. build — choose the output target, materialise, then run

**Decide the output format with the user first** — don't default silently.
Choose the BioCypher backend with `biotope build --target {csv,neo4j}` (default
`csv`): generic CSV/tabular, or Neo4j bulk-import (which adds a
`neo4j-admin-import-call.sh`). Other backends are set in
`build/config/biocypher_config.yaml`; the Neo4j import recipe and backend notes
live in `references/output-targets.md`.

```bash
biotope build --target neo4j        # strict: refuses any unresolved slot
uv run python build/create_knowledge_graph.py
```

`build` writes plain, committable Python + YAML under `build/`
(`config/schema_config.yaml`, an adapter per mapping, and
`create_knowledge_graph.py`) and prints the resolved `target (dbms)`. The entry
point regenerates `build/biocypher-out/` from scratch each run (so re-running
after a target change is clean), emits `schema_info.yaml` for downstream
querying, and writes `build_metrics.json` (orphaned edges + compile drops).

### 6. Verify — never trust the exit code, report the format honestly

```bash
biotope view      # target (dbms), node + edge counts, orphaned-edge metrics, schema diff
biotope status    # tracked files still consistent?
```

A build can succeed while dropping edges whose endpoints don't resolve to a node.
`biotope view` prints the active target plus orphaned-edge and compile-drop
counts (also in `build/biocypher-out/build_metrics.json`) — read them, don't just
trust the exit code. A relation that should have thousands of edges but emits
dozens means an id-namespace mismatch; fix the ids upstream (see
`references/reliability.md`), don't patch generated files. **Never claim a graph
"works" without `biotope view` confirming non-empty, sane outputs, and state the
target it reports** rather than guessing the format.

## Reliability principles — read these

The difference between a graph that answers questions and one that quietly
loses a third of them is almost always set *before* the build, in how ids and
data are prepared. `references/reliability.md` holds the durable principles:
canonicalize ids up front, audit auto-alignments, verify edge survival, never
fabricate data to satisfy a slot, keep manifest and data in sync, treat the
schema as a contract. Read it on any non-trivial graph.

## House rules

- Use flags, never interactive prompts; never hand-edit `.biotope/` files or the
  generated `build/` adapters and `create_knowledge_graph.py`. If output looks
  wrong, fix the input (purpose, mapping, data) and re-run. The one editable
  thing under `build/` is `config/biocypher_config.yaml` (output target,
  ontology) — `build` preserves it across rebuilds.
- Use `biotope add` / `commit` / `mv` for metadata, not raw file moves — they
  keep the git-tracked manifests consistent.
- Keep `purpose:` honest — it's the one sentence a future reader relies on.

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
