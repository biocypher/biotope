# Tutorial: build your first knowledge graph

This 15-minute tutorial turns four small public files into a knowledge graph:
two CSVs of US airports and flights, one markdown file with airport notes, and
a CSV derived from those notes. The result contains about 3,400 airports,
5,400 flight routes, 5 airlines, and 12 "is a hub for" relations.

Croissant-baker can describe the CSV schemas directly. The markdown file needs
an extra step because it contains useful facts but has no schema. We will
extract those facts into a CSV, first as a manual task and then with an agent.
Both paths produce the same file and use the same mapping.

If you have the [biotope plugin](plugin.md) installed, jump to the
[agent shortcut](#agent-shortcut) at the end. Invoke `/biotope-croissant` or
ask your agent to help build the graph.

## Prerequisites

Recommended path: install the [biotope plugin](plugin.md) in your coding agent.

To use the CLI directly, install it:

```bash
uv add "biotope>=0.8.0"        # if in uv-managed venv
# OR
pipx install "biotope>=0.8.0"  # global installation
```

You can also use `uvx biotope init` with no prior install. Below we use `uvx` for initialisation (from a parent directory) and `uv` inside the project. Substitute your own package workflow if you prefer.

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
files), `mappings/` (empty; for the semantic mapping files), and a minimal
`pyproject.toml`. A coding agent picks up the project contract from the
biotope plugin skills (biotope-croissant → biocypher → biochatter). A fresh `git` repo is initialised in the same
directory.

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

```console { .terminal .no-copy }
$ uv run biotope queue
RAW (1) — needs processing
  • data/notes/airports-notes

PROCESSED (1) — ready to map
  • data/flights

MAPPED (0) — in the KG
  (none)
```

Two things to notice:

- `data/flights` is `processed`: croissant-baker recognised the CSVs,
  inferred their schemas, and recorded the `recordSet` and field types in the
  manifest. The dataset is ready to map.
- `data/notes/airports-notes` is `raw`: baker cannot structure free-form
  markdown. Biotope tracks the file for provenance, but the build has no schema
  to consume yet.

## 5. Process the raw input into the KG

The notes say which airlines use which airports as hubs. To put those facts in
the graph, extract them into a structured CSV. You can do this manually or ask
an agent:

!!! info "Processing"

    === "Human"

        Without an agent, read the notes and enter the facts in a CSV with
        `airport_iata`, `airline_code`, and `airline_name` columns. This
        tutorial provides the finished CSV so you can continue without doing
        that transcription:

        ```bash
        uv run biotope get \
          https://raw.githubusercontent.com/biocypher/biotope/main/docs/examples/airport-hubs.csv \
          --output-dir data/notes --no-add
        ```

        `--no-add` downloads the file without tracking it yet. Add it separately
        so you can record that it was derived from the markdown notes:

        ```bash
        uv run biotope add data/notes/airport-hubs.csv \
          --derived-from data/notes/airports-notes
        ```

    === "Agent"

        The agent reads `data/notes/airports-notes.md`, extracts
        `(airport_iata, airline_code, airline_name)` rows, and writes them to
        `data/notes/airport-hubs.csv`. Review the extracted rows before adding
        the file. The agent then records its provenance with the same command
        used in the human path:

        ```bash
        uv run biotope add data/notes/airport-hubs.csv \
          --derived-from data/notes/airports-notes
        ```

The `--derived-from` flag adds `prov:wasDerivedFrom` to the new manifest and
removes the original notes from the active `raw` queue. It does not rename or
move them. After either path, the queue looks like:

```bash
uv run biotope queue
```

```console { .terminal .no-copy }
$ uv run biotope queue
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

!!! info "Declaring intent"

    === "Human"

        Launch the wizard with no arguments:

        ```bash
        uv run biotope map
        ```

        The project has data and purpose but no fully declared intent yet, so
        the wizard opens with an intent-capture prompt:

        ```console { .terminal .no-copy }
        $ uv run biotope map

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
        next. It prints each croissant's record sets, field types, and
        a few sample rows so you can decide which dataset feeds which
        slot. The same view is available non-interactively as
        `uv run biotope map inspect <croissant>`.

    === "Agent"

        The agent records the same intent without opening the wizard. If the
        requested representation is ambiguous, it asks before continuing.

        ```bash
        uv run biotope map \
          --entity airport --entity airline \
          --relation number_of_flights --relation is_hub_for
        ```

        This appends to `required_entities` / `required_relations` in
        `.biotope/project.yaml` and exits without entering the wizard.

After this step, `.biotope/project.yaml` declares four slots that the
rest of the walkthrough must resolve.

## 7. Bind each slot to real data

With the four slots declared, the wizard's main view is the slot table.
Re-enter it (or stay in it, if you came straight from step 6):

```bash
uv run biotope map
```

```console { .terminal .no-copy }
$ uv run biotope map

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

!!! info "Binding an entity"

    === "Human"

        ```console { .terminal .no-copy }
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

        The scaffold's inspector appendix gives the agent the field catalogue
        for these choices. The same data is available from
        `uv run biotope map inspect <croissant> --json`.

### Binding the `is_hub_for` relation → airport-hubs croissant

!!! info "Binding a relation"

    === "Human"

        ```console { .terminal .no-copy }
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
        flights mapping. Both sides mint `iata:<code>` IDs, so
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

### Bind the remaining two slots

`airline` (slot 2) and `number_of_flights` (slot 3) follow the same
pattern. Pick the slot, select the croissant (`airport-hubs` for `airline` and
`flights` for `number_of_flights`), then answer the prompts. The
`number_of_flights` relation binds against the `flights-airport` record
set with `origin` → `destination` as the endpoints and `count` as a
property. When all four slots show ✓, the wizard prints:

```console { .terminal .no-copy }
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

This creates a self-contained BioCypher project under `build/`, including
`schema_config.yaml`, one adapter per mapping, and
`create_knowledge_graph.py`. The command stops if any mapping slot remains
unresolved.

## 9. Run the graph build

```bash
uv run python build/create_knowledge_graph.py
```

BioCypher writes node and edge CSVs to `build/biocypher-out/`. You may
see `WARNING -- Duplicate node type airport found`. This is expected because
two mappings emit Airport nodes: rich nodes from `flights` and ID-only nodes
from `airport-hubs`. The writer merges them.

## 10. Look at the result

```bash
uv run biotope view
```

```console { .terminal .no-copy }
$ uv run biotope view

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
and 5,366 flight routes. Extracting the unstructured notes into a CSV added
5 airlines and 12 "is a hub for" edges.

The CSVs in `build/biocypher-out/` are ready to be imported into Neo4j
(`neo4j-admin database import`), DuckDB, or any graph store BioCypher
targets. See the BioCypher docs for import instructions.

## Agent shortcut

Everything above is delegable. After `biotope init`, `cd` into the project,
open your agent with the [biotope plugin](plugin.md) installed,
invoke `/biotope-croissant` or say:

> *What does biotope do? Help me build the KG.*

The agent picks up the skill contract, runs
`biotope queue --json` to see what's tracked, decides whether to leave
raw items alone or process them, scaffolds and resolves mappings using
`biotope map inspect --json` for the field catalogue, and runs the build.
The contract is the CLI; no agent needs to import any biotope Python.

Without an agent, extracting facts from markdown, PDFs, or other unstructured
sources remains manual. An agent can perform that extraction, but you should
review the structured output before it enters the graph.

The remaining work is deterministic. The agent resolves mapping slots against
the inspector output, previews the mappings, proposes alignments, builds the
graph, and checks the result.
