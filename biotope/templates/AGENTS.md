# Agent instructions for this biotope project

You are working inside a `biotope` project — a Croissant-driven knowledge-graph
workspace. Always reach for the CLI; never edit configs by hand and never
import biotope's Python modules directly. Every action a user could take is
exposed as a flag on a biotope command.

## Hard rules — read first

1. **Never modify `required_entities` or `required_relations` without the
   user's explicit instruction.** The user's stated schema is the contract.
   Resolve mapping *slots* against that schema; do not restructure the schema
   to fit a convenient mapping. Any concept named in `purpose:` that you are
   about to encode as anything *other* than a first-class entity/relation is a
   stop sign — ask first.
2. **Data lives inside the project.** A biotope project owns its data. The
   manifest at `.biotope/datasets/<rel>.jsonld` addresses `<project>/<rel>/`,
   so files outside the project tree are not ingestible. Acceptable shapes:
   copy into the project, or fetch via `biotope get <url>`. Symlinks that
   point outside the project root are rejected — they break self-containment
   (collaborators get a broken link) and let the target's contents drift
   without changing the tracked manifest.
3. **`--clear-entities` / `--clear-relations` are destructive.** They erase
   the user's declared schema. Use only when the user has explicitly asked you
   to drop and rewrite intent — never as a tidy-up before re-encoding.

## The canonical workflow

```
biotope init  →  biotope add  →  biotope map  →  biotope build
```

- `init` creates the project skeleton and `.biotope/project.yaml`.
- `add` brings each dataset under the project and writes its Croissant
  metadata. **Do this before mapping**, so you can map against fields and
  record sets that actually exist.
- `map` does two things: captures intent (`--purpose`, `--entity`,
  `--relation`) into `project.yaml`, *and* authors per-dataset mappings under
  `mappings/` that resolve those entities/relations against real data.
- `build` materialises a runnable BioCypher project from every mapping.

**Multi-mapping projects are the norm.** A real biotope holds N
`mappings/*.mapping.yaml` files — one per logical dataset — and `build`
streams nodes/edges from all of them.

### Alternative: intent first, then data

If the user wants to capture intent before any data is available (e.g. as a
shopping list for `biotope discover` or manual data sourcing), it's fine to
run `biotope map --purpose ... --entity ... --relation ...` first. But
**author the per-dataset mappings only after `biotope add`** — mapping
without knowing the data leads to slot resolutions that don't match real
fields.

## Start every session by orienting

Before any technical work, elicit the user's **competence questions** in their
own words:

1. What concrete domain questions should this graph answer?
2. What entity types (the nouns of the user's domain) are involved?
3. What relations between them matter?
4. Which datasets does the user already have on disk, and which would need to
   be discovered or generated?

You may already find some of these answers in `.biotope/project.yaml`. If so,
confirm them with the user before assuming they're current. **Never silently
overwrite or `--clear-*` what's already there** (see Hard rule 1).

Then check the pipeline queue:

```bash
biotope queue          # human-readable; raw / processed / mapped sections
biotope queue --json   # same shape, machine-readable
```

The queue is what every dataset currently is in the pipeline:

- **raw**: croissant-baker couldn't fully describe the file (PDFs, URLs,
  documents). The agent's job is to process these into a derived artifact.
- **processed**: schema is concrete; ready to be mapped into the KG.
- **mapped**: a resolved mapping exists; ingestable AND configured.

Datasets that something else `prov:wasDerivedFrom` are hidden from the active
raw section — they've been consumed already. Don't re-process them. If you
add a derived artifact (e.g. a JSON extracted from a PDF), record the link:

```bash
biotope add data/extracted/annual_report.json --derived-from data/raw/annual_report.pdf
```

This is how the agent says "I'm done with that raw input" without renaming
or moving anything. Status auto-transitions in the happy path:

- `biotope add` classifies new manifests as `raw` or `processed` from the
  baked Croissant (record set with fields → processed, else raw).
- `biotope map` flips a dataset to `mapped` when a save produces a fully
  resolved mapping.

Manual override exists for corrections:

```bash
biotope mark <dataset> processed --derived-from <other_dataset>
```

But the auto-transitions cover the common path — reach for `mark` only when
the heuristic is wrong or a rare correction is needed.

## Bring data in

**Step 1 — copy the source folder into the project.** Data must live under the
project root before `biotope add` can address it (see Hard rule 2). If the
user points at a directory outside the project, copy it in first; don't try
to make `biotope add` accept external paths.

```bash
cp -r /elsewhere/source_pull data/source_pull
```

For files coming from URLs use `biotope get <url>` instead — it fetches them
into the project tree directly.

**Step 2 — `biotope add` on the whole copied folder, in one call.**

```bash
biotope add data/source_pull \
  --license "CC-BY-4.0" \
  --creator "Source Org" \
  --description "..."
```

`biotope add` runs croissant-baker on the directory (recursing automatically)
and writes one manifest at `.biotope/datasets/data/source_pull.jsonld`
covering the whole subtree. It also writes `<dir>/.biotope.yaml` for bulk
human review; apply edits with:

```bash
biotope annotate apply data/source_pull
biotope annotate apply data/source_pull --set creator="Source Org"
```

Pass any metadata the baker *cannot* infer (license, creator, creator email,
description, access restrictions, legal obligations, collaboration details,
RAI metadata) as flags on the `add` call.

### Choosing what to `add`

**Default: one call, on the highest folder that is the whole pull.** If the
user copied a directory containing many subdirectories
(`data/source_pull/{primary/, secondary/, links/, …}`), run
`biotope add data/source_pull` — a single manifest covers the whole tree,
with FileSet globs handling the per-subdirectory structured files and
FileObjects handling stragglers.

```bash
biotope add data/source_pull        # one call, one manifest, one dataset
```

**Do not** subdivide by running `add` per subdirectory unless the user
explicitly wants each subdirectory tracked as its own dataset (rare; only
makes sense when subdirectories are unrelated data sources that happen to
share a parent). The multi-file manifest model handles internal structure
fine without splitting.

**Anti-pattern**: pointing `biotope add` at individual files inside a
partitioned table (`data/source_pull/primary/part-0000.parquet`) — you'll
get one manifest per file. Stop, delete the generated manifests, and add
the top-level folder instead.

### Finding more data

To find datasets the user does *not* yet have:

```bash
biotope discover
```

This consults the BioCypher-adapter registry against the `required_entities`
in `project.yaml` and ranks candidates.

## Record what you learn

Populate the project document via `biotope map` intent flags — never edit
YAML by hand:

```bash
biotope map --purpose "..." \
            --entity book --entity author --entity library \
            --relation "which books were written by which authors" \
            --relation "which books are held by which libraries"
```

(Generic example — replace with the user's actual domain.)

When any intent flag is present, `biotope map` runs **non-interactively**: it
writes to `.biotope/project.yaml` (or `./project.yaml` if the project was
initialised with `--visible`) and exits. With no flags, it would launch the
interactive wizard — agents should always use flags instead.

`--entity` and `--relation` accept **free text**. Use a short label if the
schema vocabulary is already settled (`book_written_by_author`); otherwise
capture the user's wording verbatim (`which books were written by which authors`)
— keys are normalised to `snake_case` automatically. Run `biotope map --show`
at any time to print the current intent plus mapping progress.

Adding to the schema is always safe. **Removing** is not: see Hard rule 1 and
Hard rule 3 — `--clear-entities` and `--clear-relations` need the user's
explicit say-so.

## Author the mapping

biotope does **not** infer which record set should be a `book` (or whatever
entity type) or which field is the `id`. You do. Author one mapping file per
logical dataset; `build` will stream them all.

### 1. Generate an unresolved scaffold

```bash
biotope map scaffold .biotope/datasets/<name>.jsonld
```

This writes `mappings/<name>.mapping.yaml` with one slot per entity and
relation you declared via `biotope map --entity / --relation`, plus a YAML
comment appendix listing every record set, field kind, identifier-like
candidate, explode-eligible array, and a few sample rows. The slots
themselves are unresolved placeholders — they don't even pick a record set.

### 2. Inspect (optional, JSON form for agents)

```bash
biotope map inspect .biotope/datasets/<name>.jsonld --json
```

Use this to enumerate record sets and fields when the appendix isn't enough
context to decide. Never run `biotope build` first hoping for an error
message — `inspect` and `preview` are the canonical evidence views.

### 3. Edit the YAML directly

Each entity slot needs `record_set`, `scan` (`row` or `{explode: <field>}`),
and an `id` selector. Selectors take `field`, optional `transform`
(`passthrough`, `as_curie`, `hash_id`), and optional `args`. Reusable ID
selectors live under top-level `ids:` and can be referenced via `use:`.

```yaml
entities:
  book:
    record_set: books
    scan: row
    id:
      field: isbn
      transform: as_curie
      args: { prefix: isbn }
    properties:
      title: title
```

Relation endpoints must name the referenced entity:

```yaml
relations:
  book_written_by_author:
    record_set: authorships
    source: { entity: book,   field: isbn,       transform: as_curie, args: { prefix: isbn } }
    target: { entity: author, use:   author_curie }
```

### 4. Validate before building

```bash
biotope map preview --json
```

With no path, `preview` walks **every** mapping under `mappings/` — that's
the expected shape of a project. Lists unresolved slots, validation findings,
the projected BioCypher schema, and sample emitted tuples. Iterate until
`unresolved_slots` is empty and `findings` contain no errors. Cross-mapping
equivalences are still proposed with:

```bash
biotope propose-alignment mappings/*.mapping.yaml
```

Do not invent CURIE prefixes or entity types — capture what the user actually
said, or leave the slot for them to fill.

## Build the graph

```bash
biotope build
```

This invokes the deterministic backend: read every mapping + optional
alignment, stream rows via DuckDB, write a runnable BioCypher project that
emits nodes and edges from **all** mappings (not just the first). `build` is
**strict** — it refuses to compile any mapping with unresolved slots or the
legacy `nodes`/`edges` schema. The output is `build/config/schema_config.yaml`
(generated with `namespace` and autogenerated `input_label`), one
`build/generated/<stem>/adapter.py` per mapping, and
`build/create_knowledge_graph.py` — plain Python and YAML the user can commit,
version, and rebuild without you.

## Inspect and report

After every build:

```bash
biotope status      # are tracked files still consistent?
biotope view        # node and edge counts, schema diff
biotope benchmark   # quality / coverage metrics
```

Report counts and obvious anomalies back to the user. Never claim a build
"works" without `biotope view` confirming non-empty outputs.

## House rules

- Use flags, not interactive prompts. If you'd be tempted to run
  `biotope init --interactive`, prefer setting the flags directly.
- Prefer `biotope annotate apply` over interactive editing when a dataset
  already has a `.biotope.yaml` scaffold.
- Never bypass git-tracked metadata — `biotope add`, `biotope commit`,
  `biotope mv` exist for that.
- If a command's output looks wrong, fix the inputs (purpose, mapping,
  alignment) and re-run. Do not patch generated files by hand.
- Keep `purpose:` in `.biotope/project.yaml` honest. It's the single sentence
  someone reading this project a year from now will rely on.
