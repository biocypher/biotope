# Tutorial: explore a finished project

This tutorial explores a small finished project: six airports, five airlines, and the notes an operations desk keeps on them. The graph shows which airline uses which airport as a hub or a focus city. You see what an agent leaves in a project, then check and build it yourself. You write no code. You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and git.

## Set up

Copy the example from the Biotope release and install its environment:

<!-- x-release-please-start-version -->
```bash
git clone --depth 1 --branch biotope-v1.0.2 https://github.com/biocypher/biotope.git
```
<!-- x-release-please-end -->

```bash
cp -R biotope/examples/airports my-airports
cd my-airports
uv sync --project graph
```

## The data

The project has two kinds of data:

- `data/airports/` holds three CSV tables: the airports, the airlines, and which airline has a hub at which airport.
- `data/notes/airport-notes.md` holds the desk's notes, one section per airport. Each section states its roles in sentences such as "Hub for Delta Air Lines." and "Focus city for Alaska Airlines."

The two sources disagree once. `hubs.csv` lists Alaska Airlines as a hub at SFO, and the notes call SFO a focus city for Alaska Airlines.

## Read the project

The agent agreed the purpose with the desk, described the data, wrote an extractor for the notes and asked how to resolve the disagreement. These files hold the result:

- `.biotope/project.yaml` holds the purpose and its typical questions.
- `data/.biotope.yaml` describes each table and column.
- `graph/extraction/airport_notes.py` declares the record the notes yield and reads them with regular expressions. The notes are internal, so no model reads them.
- `graph/ASSUMPTIONS.md` lists the questions the agent asked and the desk's answers.
- `graph/alignment/airlines.py` matches the airline names in the notes to the codes in `airlines.csv`.
- `graph/mappings/role.py` takes each role from the notes and leaves out the row of `hubs.csv` they contradict.

## Extract from the notes

```bash
uv run --project graph biotope extract try airport_role_claims data/notes/airport-notes.md
```

The output lists 12 records, each with the sentence and the line it comes from. Nothing in the project changes. The agent stored the same records with `biotope extract run` in `data/extracted/airport_role_claims.jsonl`, and the graph reads them from there.

## Check and build

```bash
uv run --project graph biotope graph check
uv run --project graph biotope graph build
```

The build also prints BioCypher's log lines and, on the first run, warnings from the rdflib library. You can ignore both. The build writes 11 nodes and 12 edges to `graph/build/`: the six airports, the five airlines, and one edge for each role an airline has at an airport. `graph/build/run.json` lists one excluded record under the rule `hub_row_superseded_by_notes`: line 13 of `hubs.csv`, where Alaska Airlines is a hub at SFO. [Use the result](result.md) explains each file the build writes.

## View the topology

```bash
uv run --project graph biotope graph metagraph --report graph/build/run.json
```

Open `graph/metagraph.html` in a browser to see the node and edge types with their descriptions and counts.

## Build it with the agent

To see how an agent arrives at such a project, give it the raw data in a new folder:

```bash
mkdir -p ../my-own/data
cp -R data/airports data/notes ../my-own/data/
```

Start your agent in `my-own` and use the example's purpose:

> Use biotope to build a knowledge graph from the files in `data/`. Purpose: our operations team looks up which airlines use which airports as hubs or focus cities. Typical questions: which airlines have a hub at JFK? Where does United have hubs? Which airports are a focus city, and for which airline? The notes are internal, so extract from them with code, not with a model.

The sources leave open which of them is right about SFO and how a name in the notes matches an airline code, so expect the agent to ask. Compare its node and edge types and its exclusions with this example.
