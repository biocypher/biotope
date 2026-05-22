# Tutorial: build your first knowledge graph

A 10-minute end-to-end walk-through. We'll take three small public files —
two CSVs and a README — and turn the structured data into a runnable
knowledge graph of US airports and the flight routes between them. About
8,700 nodes and edges total; ~280 KB of input.

If you'd rather hand the wheel to an agent, jump to the [agent shortcut](#agent-shortcut)
at the end. The same biotope commands drive both flows.

## Prerequisites

```bash
uv pip install biotope
```

A `git` install on `$PATH`. Nothing else.

## 1. Scaffold a project

```bash
biotope init airports-kg \
  --purpose "Which US airports are most connected in the flight network?" \
  --no-prompt
cd airports-kg
```

This creates `.biotope/` (manifests + config), `data/` (empty; for your
files), `mappings/` (empty; for the semantic mapping files), `AGENTS.md`
(the contract any coding agent will read), and a minimal `pyproject.toml`.
A fresh `git` repo is initialised in the same directory.

## 2. Bring in the data

Three files from the
[vega-datasets](https://github.com/vega/vega-datasets) project. We download
the two CSVs into a single sub-folder so they end up under one composite
manifest, then a markdown README as a separate "unstructured" file:

```bash
biotope get https://cdn.jsdelivr.net/npm/vega-datasets/data/airports.csv \
  --output-dir data/flights --no-add
biotope get https://cdn.jsdelivr.net/npm/vega-datasets/data/flights-airport.csv \
  --output-dir data/flights --no-add
biotope add data/flights \
  --license "BSD-3-Clause" --creator "vega-datasets"

biotope get https://raw.githubusercontent.com/vega/vega-datasets/main/README.md \
  --output-dir data/notes
```

The first two downloads use `--no-add` so they land on disk without being
tracked individually; the single `biotope add data/flights` then runs
croissant-baker over the whole folder and writes one manifest at
`.biotope/datasets/data/flights.jsonld` covering both record sets. The
README, in contrast, lands as its own manifest.

## 3. Inspect the pipeline queue

```bash
biotope queue
```

```
RAW (1) — needs processing
  • data/notes/README

PROCESSED (1) — ready to map
  • data/flights

MAPPED (0) — in the KG
  (none)
```

Two things to notice:

- **`data/flights` is `processed`** — croissant-baker recognised CSVs,
  inferred their schemas, and recorded `recordSet` + field types in the
  manifest. Ready to be mapped into the KG.
- **`data/notes/README` is `raw`** — baker can't structure free-form
  markdown. The dataset is tracked (auditability, provenance) but has no
  schema for the KG build to consume.

What to do with the raw entry depends on whether a human or an agent is
driving:

=== "Human"

    The README is a description of what's in the dataset, not data to put
    into the KG. Leave it `raw`. The graph build will skip it; the
    manifest stays in the project as a tracked input.

=== "Agent"

    Extract the structured bits worth ingesting and add them as a derived
    artifact, then mark the README consumed:

    ```bash
    # Agent writes data/notes/sources.csv with columns: dataset, source_url.
    biotope add data/notes/sources.csv \
      --derived-from data/notes/README
    ```

    The `--derived-from` link records provenance via `prov:wasDerivedFrom`
    and hides the README from the active raw queue — biotope knows it's
    been consumed without renaming or moving the file. The derived CSV
    bakes as `processed`. If you want it in the KG, extend the mapping
    in step 5 to cover it; if it's a pure provenance trail, leave it
    out of the mapping and it stays tracked but un-ingested.

## 4. Declare what the graph should contain

```bash
biotope map --entity Airport --relation has_flight
```

This writes the required entities and relations into `.biotope/project.yaml`
(your *competence questions*: what nouns and verbs must the graph express).
Every mapping you author from now on must resolve `Airport` and
`has_flight` against real data — the build is strict.

## 5. Scaffold and resolve the mapping

```bash
biotope map scaffold .biotope/datasets/data/flights.jsonld
```

This writes `mappings/flights.mapping.yaml` with one unresolved slot per
declared entity/relation, plus an *inspector appendix* listing every
record set, every field with its type, and three sample rows. Open the
file: the appendix is what tells you (or your agent) which fields to use.

Replace the file contents with this resolved mapping:

```yaml
croissant: .biotope/datasets/data/flights.jsonld
entities:
  airport:
    record_set: airports
    scan: row
    id:
      field: iata
      transform: as_curie
      args: {prefix: iata}
    properties:
      name: name
      city: city
      state: state
      country: country
      latitude: latitude
      longitude: longitude
relations:
  has_flight:
    record_set: flights-airport
    scan: row
    source:
      entity: airport
      field: origin
      transform: as_curie
      args: {prefix: iata}
    target:
      entity: airport
      field: destination
      transform: as_curie
      args: {prefix: iata}
    properties:
      count: count
```

What's happening:

- `entities.airport` pulls from the `airports` record set, mints CURIEs
  like `iata:00M`, and attaches the other columns as node properties.
- `relations.has_flight` pulls from the `flights-airport` record set,
  using `origin` and `destination` (themselves `iata` codes) as endpoint
  IDs — matching the airport node IDs minted above.

=== "Human"

    Edit by hand using the inspector appendix as your field catalogue.
    Or run `biotope map` for a guided wizard that walks you through each
    slot.

=== "Agent"

    The same flow, non-interactively: an agent reads the appendix (or
    runs `biotope map inspect <croissant> --json` to get it as
    structured JSON), produces the YAML, and verifies it with
    `biotope map preview --json` before committing.

Verify the mapping is sane:

```bash
biotope map preview
```

You should see a schema panel with `airport -> Airport` and
`has_flight -> has flight`, plus sample tuples like
`('iata:00M', 'airport', {...})` and
`(None, 'iata:ABE', 'iata:ATL', 'has_flight', {'count': 853})`.

## 6. Build

```bash
biotope build
```

This generates a self-contained BioCypher project under `build/` —
`schema_config.yaml`, an adapter per mapping, and an entry-point
`create_knowledge_graph.py`. Strict: any unresolved slot would have
errored out here.

## 7. Run the graph build

```bash
python build/create_knowledge_graph.py
```

BioCypher writes node and edge CSVs to `build/biocypher-out/`. With
~3 400 airports and ~5 400 flight routes, this takes a second or two.

## 8. Look at the result

```bash
biotope view
```

```
        BioCypher build:
/.../airports-kg/build
┏━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━┓
┃ file           ┃ lines ┃ kind ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━┩
│ airport.csv    │  3376 │ node │
│ has_flight.csv │  5366 │ edge │
└────────────────┴───────┴──────┘

Total nodes: 3376  edges: 5366
```

That's your knowledge graph. The CSVs in `build/biocypher-out/` are ready
to be imported into Neo4j (`neo4j-admin database import`), DuckDB, or any
graph store BioCypher targets — see the BioCypher docs for the import
side.

## Agent shortcut

Everything above is delegable. After `biotope init`, you can `cd` into the
project and start a copilot — Claude Code, Cursor, Aider, or anything that
reads `AGENTS.md` — and say:

> "help me build the KG"

The agent reads `AGENTS.md` (already in the project root), runs
`biotope queue --json` to see what's tracked, decides whether to leave
raw items alone or process them, scaffolds and resolves mappings using
`biotope map inspect --json` for the field catalogue, and runs the build.
The contract is the CLI; no agent needs to import any biotope Python.

The clear division of labour:

- **Human-only work**: unstructured raw inputs (PDFs, notes, free-form
  documents) typically *stay* raw — there's no automation that reliably
  extracts the right structured artifact from them. Skip them or hand
  them to an agent.
- **Agent territory**: anything baker already structured is mechanical
  from there. Slot resolution against the inspector appendix, multi-axis
  mappings, cross-mapping alignment proposals — all suit non-interactive
  drivers better than a human clicking through a wizard.
