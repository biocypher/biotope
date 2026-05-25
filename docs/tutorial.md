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
tutorial, our name will be `airports` and our purpose is to "`Find which US airports are most connected and which airlines use them as their hubs.`".
Or, fully CLI-based:

```bash
uvx biotope init airports \
  --purpose "Find which US airports are most connected and which airlines use them as their hubs." \
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

You can check project status at any time using `uv run biotope status`.

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
uv run biotope queue
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

!!! Processing

````
=== "Human"

    Before LLM agents, the most reliable way to process simple unstructured
    text into the structured form required for our pipeline is manual
    curation into a structured form (such as a CSV of triples). You can
    imagine doing this here, but for this tutorial we ship the pre-extracted
    CSV so you can fetch it directly, to save time:

    ```bash
    uv run biotope get \
      https://raw.githubusercontent.com/biocypher/biotope/main/docs/examples/airport-hubs.csv \
      --output-dir data/notes --no-add
    ```

    Note the `--no-add` flag; we are acting like we'd create the file by
    hand to then add as a derivative of the unstructured markdown note.
    Running the biotope pipeline with an agent (see "Agent" tab) will allow
    us to automate the task. After we have created (or downloaded) the file,
    we need to indicate that the new file was derived from the unstructured
    version (to remove it from the queue):

    ```bash
    uv run biotope add data/notes/airport-hubs.csv \
      --derived-from data/notes/airports-notes
    ```

=== "Agent"

    If you use an agent to run the biotope pipeline, it will be instructed
    and figure out to read `data/notes/airports-notes.md`, extract the
    `(airport_iata, airline_code, airline_name)` triples it mentions, and
    write the result to `data/notes/airport-hubs.csv`. Different agents
    might choose to do this differently; through the biotope scaffolding,
    the results should be equivalent. This will result in the same state as
    the first command in the human example.

    Then, the agent should also record the provenance link by calling the
    same command as in the human example:

    ```bash
    uv run biotope add data/notes/airport-hubs.csv \
      --derived-from data/notes/airports-notes
    ```
````

The `--derived-from` flag stamps `prov:wasDerivedFrom` into the new manifest and
hides the original notes from the active `raw` queue — biotope knows they've
been consumed without renaming or moving them.  Either way, after this step the
queue looks like:

```
PROCESSED (2) — ready to map
  • data/flights
  • data/notes/airport-hubs  (derived from: data/notes/airports-notes)

Raw inputs already consumed (their derivatives are in the queue): 1
  • data/notes/airports-notes
```

The "Raw inputs already consumed" footer is the provenance trail. The original
notes stay in the project as a tracked input; the structured CSV is what gets
mapped.

## 6. Declare what the graph should contain

To represent the data according to our purpose, the graph should express a
small, fixed vocabulary: this could be, for instance, two nouns (`airport`,
`airline`) and two verbs (`number of flights`, `is hub for`).

!!! Declaring intent

````
=== "Human"

    Launch the wizard with no arguments:

    ```bash
    uv run biotope map
    ```

    The project has data and purpose but no fully declared intent yet, so
    the wizard opens with an intent-capture prompt:

    ```
    ╭───────────────── Current intent ─────────────────╮
    │ purpose: Find which US airports are most         │
    │          connected and which airlines use them   │
    │          as their hubs.                          │
    │ entities: (none)                                 │
    │ relations: (none)                                │
    ╰──────────────────────────────────────────────────╯

    Enter a new purpose, or press Enter to keep the current one.
    Purpose: ⏎

    Add entities one per line. Press Enter on an empty line to stop.
    Entity name: airport
    Entity name: airline
    Entity name: ⏎

    Add relations one per line. Press Enter on an empty line to stop.
    Relation name: number of flights
    Relation name: is hub for
    Relation name: ⏎

    💾 Saved intent to .biotope/project.yaml
    ```

    Names are normalised to snake_case behind the scenes
    (`number of flights` → `number_of_flights`).

    If you're unsure what data you have to bind these to, pick
    `[v] view data` from the slot menu the wizard drops you into
    next — it prints each croissant's record sets, field types, and
    a few sample rows so you can decide which dataset feeds which
    slot. The same view is available non-interactively as
    `uv run biotope map inspect <croissant>`.

=== "Agent"

    Same effect, non-interactively — in auto-mode, the agent will decide on
    an adequate representation and initialise accordingly. In ambiguous
    cases, it is instructed to check with the user.

    ```bash
    uv run biotope map \
      --entity airport --entity airline \
      --relation number_of_flights --relation is_hub_for
    ```

    This appends to `required_entities` / `required_relations` in
    `.biotope/project.yaml` and exits without entering the wizard.
````

After this step, `.biotope/project.yaml` declares four slots that the
rest of the walkthrough must resolve.

## 7. Bind each slot to real data

With the four slots declared, the wizard's main view is the slot table.
Re-enter it (or stay in it, if you came straight from step 6):

```bash
uv run biotope map
```

```
        Declared slots — 0/4 resolved (project-wide)
┏━━━┳━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ # ┃   ┃ Kind     ┃ Name              ┃ Bound in   ┃
┡━━━╇━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ 1 │ ○ │ entity   │ airport           │ —          │
│ 2 │ ○ │ entity   │ airline           │ —          │
│ 3 │ ○ │ relation │ number_of_flights │ —          │
│ 4 │ ○ │ relation │ is_hub_for        │ —          │
└───┴───┴──────────┴───────────────────┴────────────┘
Enter a slot number to bind it, or one of:
  [v] view data    [i] edit intent    [q] save and quit
Selection (1):
```

Each slot is bound the same way: pick the slot number → pick the
croissant that has the right fields → answer a handful of prompts about
record set, scan, id, and properties. The wizard validates and autosaves
after every step. Below are two representative bindings (one entity,
one relation); the other two follow the same pattern.

### Binding the `airport` entity → flights croissant

!!! Binding an entity

````
=== "Human"

    ```
    Selection (1): 1

    Pick a croissant to bind entity `airport`
    # │ Croissant                                  │ Match
    1 │ .biotope/datasets/data/flights.jsonld      │   2
    2 │ .biotope/datasets/data/notes/airport-hubs… │   1
    Croissant: 1

    Record sets
    # │ Name             │ Fields
    1 │ airports          │ iata, name, city, state, country, latitude, longitude
    2 │ flights-airport   │ origin, destination, count
    Pick record set (1): 1

    Scan kind — (r)ow, (e)xplode one, (m)ulti-axis (r): r

    Namespace (optional): ⏎

    Choose action (field): field
    ID field: iata
    Transform [passthrough]: as_curie
    CURIE prefix: iata

    Property fields (comma-separated): name, city, state, country, latitude, longitude

    💾 Saved mappings/flights.mapping.yaml
    ```

=== "Agent"

    An agent skips the wizard and writes the binding straight into
    the mapping file (scaffolding it first with
    `uv run biotope map scaffold .biotope/datasets/data/flights.jsonld`
    if it doesn't exist yet):

    ```yaml
    # mappings/flights.mapping.yaml
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
    ```

    The scaffold's inspector appendix — or
    `uv run biotope map inspect <croissant> --json` — gives the agent
    the field catalogue to ground these picks.
````

### Binding the `is_hub_for` relation → airport-hubs croissant

!!! Binding a relation

````
=== "Human"

    ```
    Selection (4): 4

    Pick a croissant to bind relation `is_hub_for`
    # │ Croissant                                  │ Match
    1 │ .biotope/datasets/data/notes/airport-hubs… │   2
    2 │ .biotope/datasets/data/flights.jsonld      │   0
    Croissant: 1

    Pick record set (1): 1            # airport-hubs
    Scan kind (r/e/m) (r): r

    ── Source endpoint ──
    Entity: airport
    ID field: airport_iata
    Transform: as_curie
    CURIE prefix: iata

    ── Target endpoint ──
    Entity: airline
    ID field: airline_code
    Transform: as_curie
    CURIE prefix: airline

    Property fields (comma-separated, blank for none): ⏎

    💾 Saved mappings/airport-hubs.mapping.yaml
    ```

    The `airport` endpoint reuses the entity already bound in the
    flights mapping — both sides mint `iata:<code>` IDs, so
    BioCypher dedups them at build. The `airline` endpoint is the
    first reference to that entity; bind its full properties when
    you do slot 2.

=== "Agent"

    ```yaml
    # mappings/airport-hubs.mapping.yaml
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
````

### Bind the remaining two slots

`airline` (slot 2) and `number_of_flights` (slot 3) follow the same
pattern — pick the slot, pick the croissant (airport-hubs for `airline`,
flights for `number_of_flights`), and answer the prompts. The
`number_of_flights` relation binds against the `flights-airport` record
set with `origin` → `destination` as the endpoints and `count` as a
property. When all four slots show ✓, the wizard prints:

```
All slots resolved. Run `biotope build` to generate the BioCypher project.
```

### A note on the two `airport` bindings

The flights mapping owns the rich Airport records (full properties); the
airport-hubs mapping declares a *minimal* Airport (id only) so its
`is_hub_for` relation has something to point at on the source side. Both
mint Airport IDs the same way (`iata:<code>`), so BioCypher's writer
dedups the two emissions into one Airport node per IATA code, merging
properties from the richer side.

### Verify

```bash
uv run biotope map preview
```

You should see resolved slots and sample tuples like
`('iata:00M', 'airport', {...})`,
`(None, 'iata:ABE', 'iata:ATL', 'number_of_flights', {'count': 853})`,
and `('airline:DL', 'airline', {'name': 'Delta Air Lines'})`.

## 8. Build

```bash
uv run biotope build
```

This generates a self-contained BioCypher project under `build/` —
`schema_config.yaml`, an adapter per mapping, and an entry-point
`create_knowledge_graph.py`. Strict: any unresolved slot would have
errored out here.

## 9. Run the graph build

```bash
uv run python build/create_knowledge_graph.py
```

BioCypher writes node and edge CSVs to `build/biocypher-out/`. You may
see `WARNING -- Duplicate node type airport found` — that's expected:
two mappings emit Airport nodes (the rich ones from `flights` and the
ID-only ones from `airport-hubs`), and the writer merges them.

## 10. Look at the result

```bash
uv run biotope view
```

```
                BioCypher build:
/.../airports/build
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━┓
┃ file                 ┃ lines ┃ kind ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━┩
│ airline.csv          │     5 │ node │
│ airport.csv          │  3376 │ node │
│ is_hub_for.csv       │    12 │ edge │
│ number_of_flights.csv│  5366 │ edge │
└──────────────────────┴───────┴──────┘

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
