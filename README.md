# biotope

Describe local data with croissant-baker, define a purpose and target schema, and maintain typed Python mappings and project-owned graph pipelines with version-controlled metadata. Biotope validates selected builds and writes BioCypher files. **Best used with a coding agent:** install the plugin, describe what you want the graph to answer, and let the agent run the pipeline.

|         |                                                                                                                                                                                                                                                                                                                                              |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Package | [![Latest PyPI Version](https://img.shields.io/pypi/v/biotope.svg)](https://pypi.org/project/biotope/) [![Python](https://img.shields.io/pypi/pyversions/biotope.svg)](https://pypi.org/project/biotope/) [![Docs](https://github.com/biocypher/biotope/actions/workflows/docs_mkdocs.yaml/badge.svg)](https://biocypher.github.io/biotope/) |
| Meta    | [![Apache 2.0](https://img.shields.io/pypi/l/biotope.svg)](LICENSE) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)                                                                                                         |

> **Pre-alpha.** CLI flags and APIs will change. The plugin skills are the most stable onboarding path.

## Install the plugin

Pick your agent harness. All paths use this repo: [github.com/biocypher/biotope](https://github.com/biocypher/biotope).

| Harness         | Setup                                                                                                                                    |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Claude Code** | `/plugin marketplace add biocypher/biotope` then `/plugin install biotope@biotope`                                                       |
| **Cursor**      | [Add a team marketplace](https://cursor.com/docs/plugins#add-a-team-marketplace) → import `biocypher/biotope`                            |
| **Codex**       | [Add a marketplace from the CLI](https://developers.openai.com/codex/plugins/build#add-a-marketplace-from-the-cli) pointing at this repo |

**Skills only:** copy the folder(s) you need from [`skills/`](skills/) into your project — e.g. `.cursor/skills/`, `.claude/skills/`. Start with `biotope-croissant`; add `biocypher` or `biochatter` when you reach those stages.

## Use it

The plugin ships a graph-authoring skill and separate database skills:

| Skill                 | Use when                                                            |
| --------------------- | ------------------------------------------------------------------- |
| **biotope-croissant** | Curated sources, Python mappings and selected BioCypher file builds |
| **biocypher**         | Tuning export backends, schema config, Neo4j import                 |
| **biochatter**        | Natural-language queries over a loaded graph                        |

You do not need to learn the CLI first. In chat, invoke a skill (e.g. `/biotope-croissant`) or just ask:

> *What does biotope do? I want to build a graph from my data.*

The agent reads the skill contract and runs `biotope` commands for you.

**Reference:** [biocypher.github.io/biotope](https://biocypher.github.io/biotope/)

## CLI (manual / scripting)

If you prefer the terminal or need CI, install the package in your environment.
For this unreleased integration, use both local checkouts in the same environment:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ../croissant-baker -e '.[graph]'
source .venv/bin/activate
```

Published-release installation options (the updated baker release is still required):

```bash
uvx biotope init my-kg    # no install — ephemeral venv for scaffolding
pipx install biotope      # global install
uv add biotope              # inside a uv-managed project
```

Graph authoring starts with `biotope graph scaffold`, which creates `graph/`.
Initialization and baking do not create or execute a graph.

Typical flow: `init` → `add` → `graph scaffold` → `source generate` → Python authoring → `graph check` → `graph build`. Command overview: [docs/commands.md](docs/commands.md).

**Worked example:** [tutorial](docs/tutorial.md) — a two-source join with typed mappings, provenance and BioCypher output.

## For developers

biotope is a CLI for the [BioCypher](https://biocypher.org/) ecosystem: curated Croissant → typed Python graph projects, with metadata version control.

| Layer           | Module                | Role                                                                         |
| --------------- | --------------------- | ---------------------------------------------------------------------------- |
| Project & VCS   | `biotope.commands.*`  | `init`, `add`, `commit`, `status`, `log`, `push`, `pull` — metadata workflow |
| Source metadata | `biotope.croissant.*` | Metadata models and payload-free inspection                                  |

Agent contract lives in `skills/` (not `AGENTS.md`). `biotope.graph` exposes the typed contracts; CLI verbs wrap generation, checking and explicit execution. See [how biotope works](https://biocypher.github.io/biotope/architecture/) and the [command overview](https://biocypher.github.io/biotope/commands/).

```bash
uv sync --extra dev --extra graph
node --version
uv run python -m pyright --version
uv run pyright
uv run pytest
uv run ruff check biotope tests
```

Typed authoring, topology organization and modular construction were informed by Paul Ka Po To's `kg-build-system`. This implementation uses ordinary Python and does not copy, vendor or depend on that engine.

## Copyright

Copyright © 2025–2026 BioCypher Team. [Apache 2.0](./LICENSE).
