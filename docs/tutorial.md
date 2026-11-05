# Tutorial: explore a finished project

This tutorial builds a small finished project: synthetic samples joined to the people they come from. You see what an agent leaves in a project, then check and build it yourself. You write no code. You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and git.

## Set up

Copy the example from the Biotope release and install its environment:

<!-- x-release-please-start-version -->
```bash
git clone --depth 1 --branch biotope-v1.0.0 https://github.com/biocypher/biotope.git
```
<!-- x-release-please-end -->

```bash
cp -R biotope/examples/typed_graph my-example
cd my-example
uv sync --project graph
```

Create the project with the example's purpose:

```bash
uv run --project graph biotope init . --no-prompt --purpose "A reviewer checks transformed sample scores against the people the samples come from. Typical questions: which samples belong to a person, and what is each sample's transformed score?"
```

## Register the data

The example ships a description of its two CSV files in `metadata/study.jsonld`, written by hand so that the result is the same on every machine. Register it, and generate the source packages from it:

```bash
uv run --project graph biotope source register metadata/study.jsonld --name study
uv run --project graph biotope source generate .biotope/datasets/study.jsonld --out graph/sources
```

The source packages already exist, so generation only records the source revisions in `.biotope/contracts/`. In your own project, the agent describes the data with `biotope add`, and generation writes a package for each table.

## Read the project

These files hold the decisions an agent records in code:

| File | What it does |
| --- | --- |
| `graph/sources/study/samples/schema.py` | Declares the fields of `samples.csv`, their types and the reviewed source revision |
| `graph/sources/study/samples/loader.py` | Reads the CSV file and decodes the score as a number |
| `graph/sources/__init__.py` | Selects both sources and excludes none |
| `graph/mappings/sample.py` | Doubles the score and builds the node IDs |
| `graph/pipelines/build_graph.py` | Joins samples to people and declares the rules that exclude records |

## Check and build

```bash
uv run --project graph biotope graph check
uv run --project graph biotope graph build
```

The check warns that the node and edge types use the illustrative `example:` namespace. The build also prints BioCypher's log lines and, on the first run, warnings from the rdflib library; neither affects the result. The build writes three nodes and two edges to `graph/build/`: Ada, samples s1 and s2, and the two edges between them. The doubled scores are 3.0 and 5.0. Sample s3 has no matching person and Bea has no sample, so `graph/build/run.json` lists one excluded record under each rule. [Use the result](result.md) explains each file the build writes.

## View the topology

```bash
uv run --project graph biotope graph metagraph --report graph/build/run.json
```

Open `graph/metagraph.html` in a browser to see the node and edge types with their descriptions and counts.

## Build it with the agent

To see how an agent arrives at such a project, give it the raw data in a new folder. Copy `raw/` from the example into an empty folder, start Claude Code there and use the example's purpose:

> Use biotope to build a knowledge graph from the files in `raw/`. Purpose: a reviewer checks transformed sample scores against the people the samples come from. Typical questions: which samples belong to a person, and what is each sample's transformed score?

The purpose leaves open what "transformed" means and what to do with a sample that has no person, so expect the agent to ask. Compare its node and edge types and its exclusions with this example.
