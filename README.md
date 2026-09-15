# Biotope

Biotope builds knowledge graphs from local data. It uses [croissant-baker](https://pypi.org/project/croissant-baker/)
to describe sources, generates typed Python records from reviewed Croissant metadata,
and checks project-owned loaders, mappings and graph pipelines. Builds export
[BioCypher](https://biocypher.org/) files with provenance and a record of the run.

[![PyPI](https://img.shields.io/pypi/v/biotope.svg)](https://pypi.org/project/biotope/)
[![Python](https://img.shields.io/pypi/pyversions/biotope.svg)](https://pypi.org/project/biotope/)
[![Documentation](https://github.com/biocypher/biotope/actions/workflows/docs_mkdocs.yaml/badge.svg)](https://biocypher.github.io/biotope/)
[![License](https://img.shields.io/pypi/l/biotope.svg)](LICENSE)

Biotope is under active development. The 0.9 release replaces YAML mappings with
Python graph projects; see the [migration guide](docs/migration.md).

## Install

Use Python 3.10–3.12. These commands use [uv](https://docs.astral.sh/uv/getting-started/installation/)
and a POSIX shell:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python 'biotope[graph]>=0.9,<0.10'
source .venv/bin/activate
biotope --version
```

This installs the published croissant-baker dependency automatically. Graph type
checking also needs Node.js on `PATH`; alternatively, install `pyright[nodejs]`
in this environment. See [installation](docs/installation.md) for other setups.

## Build a graph

1. Initialize a metadata project with `biotope init my-kg`, then enter `my-kg`.
1. Describe selected local data with `biotope add <path>` and review the Croissant metadata.
1. Run `biotope graph scaffold` and generate source records with
   `biotope source generate <manifest> --out graph/sources`.
1. Define the graph's purpose, topology, loaders, mappings and pipeline in Python.
1. Run `biotope graph check`, then `biotope graph build --out graph/build/review-1`.
1. Review the exported values, provenance and validation results against the research question.

The scaffold contains inactive examples to adapt. The [tutorial](docs/tutorial.md)
provides a complete synthetic project you can run immediately.

- [Typed graph guide](docs/mapping.md): source curation, authoring and validation.
- [Commands](docs/commands.md): metadata, graph and version-control workflows.
- [Architecture](docs/architecture.md): responsibilities and execution boundaries.
- [Published documentation](https://biocypher.github.io/biotope/).

## Use with a coding agent

The repository includes a `biotope-croissant` skill for this workflow and a
`biocypher` skill for standalone BioCypher projects. Follow the
[agent setup guide](docs/plugin.md) for Claude Code, Cursor or Codex.
Skills guide the agent; install the Python package in the project environment too.

## Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, checks and release conventions.
Report reproducible problems through [GitHub issues](https://github.com/biocypher/biotope/issues).

Typed authoring and modular topology construction were informed by Paul Ka Po To's
`kg-build-system`. Biotope does not depend on that engine.

Copyright © 2025–2026 BioCypher Team. [Apache 2.0](LICENSE).
