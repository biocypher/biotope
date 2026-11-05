# Get started

You use Biotope through a coding agent. You give it the data and the purpose of the graph. The agent describes the data, writes and runs the project's code, and asks you the decisions only you can make.

## Before you start

- Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Claude Code](https://code.claude.com/docs/en/setup). uv installs Python 3.10, 3.11 or 3.12 for the project when needed, and nothing else is required.
- Choose the project folder: your repository, or a new folder. Put the data in it, for example under `data/`.
- Keep each dataset at a fixed path. A file's ID in Biotope is its path, so a dataset saved to a new folder on each download gets new IDs, and the agent has to update the project.

## Install the plugin

In Claude Code, add the Biotope marketplace and install the plugin:

<!-- x-release-please-start-version -->
```text
/plugin marketplace add biocypher/biotope#biotope-v1.0.0
/plugin install biotope@biotope
```
<!-- x-release-please-end -->

Install it for your user to use it in every project. To check it, type `/` in Claude Code: `/biotope:biotope-croissant` is in the list.

## Start a project

Start Claude Code with `claude` in the project folder. Tell it where the data is and what the graph is for, for example:

> Use biotope to build a knowledge graph from the files in `data/`. It is for our institute's staff, who look up who works on which topic, in which group and on which projects.

> Use biotope to build a knowledge graph from the clinical tables and papers in `data/`. It is for our target-discovery team, who rank genes by the evidence that links them to liver fibrosis.

The agent then installs Biotope into the project's own environment:

- `graph/pyproject.toml` lists Biotope and the libraries that the project's code reads data with, and `graph/uv.lock` pins their versions. Commit both.
- Every command runs as `uv run --project graph biotope …` from the project folder. Use the same form when you run a command yourself.

[Working with the agent](agent.md) describes what happens next.

## Other agents

Cursor and Codex use the same skill. Copy the folder `skills/biotope-croissant` from the [Biotope repository](https://github.com/biocypher/biotope) into your project's `.cursor/skills/` for Cursor or `.agents/skills/` for Codex.

## Concepts

- **[Croissant](https://docs.mlcommons.org/croissant/docs/croissant-spec.html)**: a standard format for describing datasets: their files, tables and fields.
- **croissant-baker**: the tool that reads your data files and writes their Croissant description. Describing a dataset again after its data changed is a **rebake**.
- **Manifest**: the Croissant description of one dataset, in `.biotope/datasets/`. Biotope writes it; nobody edits it.
- **Annotation file**: the file next to a dataset, `.biotope.yaml`, where people and the agent write what they know about it, such as descriptions, keys, the creator and the license.
- **Table**: the rows of one file, or of one sheet or part of a file. Croissant calls it a record set.
- **Structured file**: a file that code can read into records, such as a CSV, Excel or Parquet file.
- **Unstructured document**: a file that needs reading, such as a paper or a web page. **Extraction** turns it into records.
- **Graph workspace**: the `graph/` folder, which holds the project's code and its builds.
- **Source package**: the Python folder in `graph/sources/` that reads one table or file into typed records.
- **Source revision**: a fingerprint of a source's structure: its fields, types and keys. When the structure changes, the check reports **drift**.
- **Topology**: the node and edge types of the graph, with their properties and descriptions.
- **Alignment**: deciding which records from different sources are the same thing.
- **Mapping**: a function that turns typed records into nodes and edges.
- **Provenance**: the source rows behind each node and edge.
- **Run record**: `run.json`, what one build read, selected, excluded and wrote.
- **[BioCypher](https://biocypher.org/)**: the framework that writes the Neo4j import files.
