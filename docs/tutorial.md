# Tutorial: build your first knowledge graph

A 15-minute end-to-end walk-through. We'll take four small public files —
two CSVs of US airport and flight data, one markdown file of free-text
notes about a few airports, and a derived CSV that extracts the
structured bits out of those notes — and turn them into a runnable
knowledge graph. About 3,400 airports, 5,400 flight routes, 5 airlines,
and 12 "is a hub for" relations.

The CSVs are the routine case: croissant-baker structures them, biotope
maps them, BioCypher writes them. The markdown file is the interesting
case: it has facts that belong in the graph (which airline hubs at which
airport) but no schema for biotope to act on. We'll handle that gap two
ways — once by a human reading the prose and hand-producing the CSV, once
by an agent doing the same extraction automatically. Either way, the same
file ends up in the project, and the same mapping ingests it.

If you'd rather hand the wheel to an agent for the whole walk-through,
jump to the [agent shortcut](#agent-shortcut) at the end.

## Prerequisites

```bash
uv add biotope        # if in uv-managed venv
# OR
pipx install biotope  # global installation
```

Or any other way to get biotope onto your `$PATH`. You can also use
`uvx biotope init` to use a temporary venv, requiring no prior install.
Below, we will use `uvx` for the initialisation (as it is performed in a
parent directory), and uv for venv management and running code in the
tutorial project itself. You are free to substitute your favourite
package management workflow.

## 1. Initialise a project

First run `biotope init` and choose a project name and purpose. For this
tutorial, our name will be `airports` and our purpose is to "`Find which US
airports are most connected and which airlines use them as their hubs?`".
Or, fully CLI-based:

```bash
uvx biotope init airports \
  --purpose "Find which US airports are most connected and which airlines use them as their hubs?" \
  --no-prompt
cd airports
```

This creates `.biotope/` (manifests + config), `data/` (empty; for your
files), `mappings/` (empty; for the semantic mapping files), `AGENTS.md`
(the contract any coding agent will read), and a minimal `pyproject.toml`.
A fresh `git` repo is initialised in the same directory.

Finally, we have to install the venv for our new project:

```bash
uv sync
```

## 2. Bring in the structured data

Two CSVs from the [vega-datasets](https://github.com/vega/vega-datasets)
project. We download both into a single sub-folder so they end up under
one composite manifest:

```bash
uv run biotope get https://cdn.jsdelivr.net/npm/vega-datasets/data/airports.csv \
  --output-dir data/flights --no-add
uv run biotope get https://cdn.jsdelivr.net/npm/vega-datasets/data/flights-airport.csv \
  --output-dir data/flights --no-add
uv run biotope add data/flights \
  --license "BSD-3-Clause" --creator "vega-datasets"
```

The `--no-add` on the downloads lets the files land on disk without being
tracked individually; the single `biotope add data/flights` then runs
[croissant-baker](https://github.com/MIT-LCP/croissant-baker) over the whole
folder and writes one manifest at `.biotope/datasets/data/flights.jsonld`
covering both record sets.

## 3. Bring in the unstructured notes

```bash
uv run biotope get https://raw.githubusercontent.com/biocypher/biotope/main/docs/examples/airports-notes.md \
  --output-dir data/notes
```

This file is short prose: a paragraph per airport mentioning which
airlines hub there. Useful information, but no schema for baker to
structure.

## 4. Inspect the pipeline queue

```bash
biotope queue
```

```
RAW (1) — needs processing
  • data/notes/airports-notes

PROCESSED (1) — ready to map
  • data/flights

MAPPED (0) — in the KG
  (none)
```

Two things to notice:

- **`data/flights` is `processed`** — croissant-baker recognised the
  CSVs, inferred their schemas, and recorded `recordSet` + field types
  in the manifest. Ready to be mapped.
- **`data/notes/airports-notes` is `raw`** — baker can't structure
  free-form markdown. The file is tracked (auditability, provenance) but
  has no schema for the build to consume.

## 5. Process the raw input into the KG

The notes contain real schema-shaped facts — which airlines hub at which
airports — that belong in the graph. Getting them in requires extracting
a structured CSV from the prose. That extraction is the boundary between
the two paths:

=== "Human"

````
Reading prose and producing a clean CSV is fast for one human and
impossible to automate without an agent. For this tutorial we ship
the pre-extracted CSV so you can fetch it directly:

```bash
biotope get \
  https://raw.githubusercontent.com/biocypher/biotope/main/docs/examples/airport-hubs.csv \
  --output-dir data/notes
```

In a real project, you'd open the markdown in an editor and write
the same CSV yourself. (Hand the wheel to an agent — next tab — and
you skip this step entirely.)
````

=== "Agent"

````
Have your agent read `data/notes/airports-notes.md`, extract the
`(airport_iata, airline_code, airline_name)` triples it mentions,
and write the result to `data/notes/airport-hubs.csv`. Then record
the provenance link:

```bash
biotope add data/notes/airport-hubs.csv \
  --derived-from data/notes/airports-notes
```

The `--derived-from` flag stamps `prov:wasDerivedFrom` into the new
manifest and hides the original notes from the active `raw` queue —
biotope knows they've been consumed without renaming or moving them.
````

Either way, after this step the queue looks like:

```
PROCESSED (2) — ready to map
  • data/flights
  • data/notes/airport-hubs  (derived from: data/notes/airports-notes)

Raw inputs already consumed (their derivatives are in the queue): 1
  • data/notes/airports-notes
```

The "Raw inputs already consumed" footer (visible only on the agent path,
because the human path doesn't link the CSV back to the markdown) is the
provenance trail. The original notes stay in the project as a tracked
input; the structured CSV is what gets mapped.

## 6. Declare what the graph should contain

```bash
biotope map --entity Airport --entity Airline \
            --relation has_flight --relation is_hub_for
```

This writes the required entities and relations into
`.biotope/project.yaml` (your *competence questions*: what nouns and
verbs must the graph express). Every mapping you author from now on must
resolve `Airport`, `Airline`, `has_flight`, and `is_hub_for` against
real data — the build is strict.

## 7. Scaffold and resolve the mappings

```bash
biotope map scaffold .biotope/datasets/data/flights.jsonld
biotope map scaffold .biotope/datasets/data/notes/airport-hubs.jsonld
```

Each scaffold writes a mapping file under `mappings/` with one slot per
declared entity/relation, plus a comment-style *inspector appendix*
listing every record set, every field with its type, and three sample
rows. That appendix is what tells you (or your agent) which fields to
use.

Replace `mappings/flights.mapping.yaml` with:

```yaml
croissant: .biotope/datasets/data/flights.jsonld
entities:
  airport:
    record_set: airports
    scan: row
    id: {field: iata, transform: as_curie, args: {prefix: iata}}
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
    source: {entity: airport, field: origin, transform: as_curie, args: {prefix: iata}}
    target: {entity: airport, field: destination, transform: as_curie, args: {prefix: iata}}
    properties:
      count: count
```

And `mappings/airport-hubs.mapping.yaml` with:

```yaml
croissant: .biotope/datasets/data/notes/airport-hubs.jsonld
entities:
  airport:
    record_set: airport-hubs
    scan: row
    id: {field: airport_iata, transform: as_curie, args: {prefix: iata}}
  airline:
    record_set: airport-hubs
    scan: row
    id: {field: airline_code, transform: as_curie, args: {prefix: airline}}
    properties:
      name: airline_name
relations:
  is_hub_for:
    record_set: airport-hubs
    scan: row
    source: {entity: airport, field: airport_iata, transform: as_curie, args: {prefix: iata}}
    target: {entity: airline, field: airline_code, transform: as_curie, args: {prefix: airline}}
```

What's happening across the two files:

- The `flights` mapping owns the rich Airport records (full properties)
  and the `has_flight` relation.
- The `airport-hubs` mapping declares a *minimal* Airport (id only — it's
  just there so the `is_hub_for` relation has something to point at on
  the source side) and introduces the new Airline entity + `is_hub_for`
  edges.
- Both mappings mint Airport node IDs the same way (`iata:<code>`), so
  BioCypher's writer dedups the two emissions into one Airport node per
  IATA code, merging properties from the richer side.

=== "Human"

```
Edit the YAML files by hand, using each scaffold's inspector
appendix as your field catalogue. Or run `biotope map` for a
guided wizard that walks you through each slot interactively.
```

=== "Agent"

```
Same flow, non-interactively: an agent reads the appendix (or runs
`biotope map inspect <croissant> --json` to get it as structured
JSON), produces the YAML, and verifies with
`biotope map preview <mapping_path> --json` before committing.
```

Verify each mapping in turn:

```bash
biotope map preview mappings/flights.mapping.yaml
biotope map preview mappings/airport-hubs.mapping.yaml
```

You should see resolved slots and sample tuples like
`('iata:00M', 'airport', {...})`,
`(None, 'iata:ABE', 'iata:ATL', 'has_flight', {'count': 853})`, and
`('airline:DL', 'airline', {'name': 'Delta Air Lines'})`.

## 8. Build

```bash
biotope build
```

This generates a self-contained BioCypher project under `build/` —
`schema_config.yaml`, an adapter per mapping, and an entry-point
`create_knowledge_graph.py`. Strict: any unresolved slot would have
errored out here.

## 9. Run the graph build

```bash
python build/create_knowledge_graph.py
```

BioCypher writes node and edge CSVs to `build/biocypher-out/`. You may
see `WARNING -- Duplicate node type airport found` — that's expected:
two mappings emit Airport nodes (the rich ones from `flights` and the
ID-only ones from `airport-hubs`), and the writer merges them.

## 10. Look at the result

```bash
biotope view
```

```
        BioCypher build:
/.../airports/build
┏━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━┓
┃ file           ┃ lines ┃ kind ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━┩
│ airline.csv    │     5 │ node │
│ airport.csv    │  3376 │ node │
│ has_flight.csv │  5366 │ edge │
│ is_hub_for.csv │    12 │ edge │
└────────────────┴───────┴──────┘

Total nodes: 3381  edges: 5378
```

That's your knowledge graph. The structured CSVs gave you 3,376 airports
and 5,366 flight routes. The unstructured notes — only because they were
extracted into a structured CSV first — gave you 5 airlines and 12
"is a hub for" edges that wouldn't otherwise be in the KG.

The CSVs in `build/biocypher-out/` are ready to be imported into Neo4j
(`neo4j-admin database import`), DuckDB, or any graph store BioCypher
targets — see the BioCypher docs for the import side.

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

- **Pure-human work, with no automation possible**: extracting structured
  facts from unstructured inputs like markdown, PDFs, or natural-language
  notes. Without an agent, this stays manual — or stays out of the KG
  entirely.
- **Agent territory**: the extraction above, plus everything mechanical
  from there. Slot resolution against the inspector appendix, multi-axis
  mappings, cross-mapping alignment proposals — all suit non-interactive
  drivers better than a human clicking through a wizard.
