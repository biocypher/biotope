# biotope

Turn tables, CSVs, and mixed biomedical data into a queryable knowledge graph — with version-controlled metadata. **Best used with a coding agent:** install the plugin, describe what you want the graph to answer, and let the agent run the pipeline.

|         |                                                                                                                                                                                                                                                                                                                                              |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Package | [![Latest PyPI Version](https://img.shields.io/pypi/v/biotope.svg)](https://pypi.org/project/biotope/) [![Python](https://img.shields.io/pypi/pyversions/biotope.svg)](https://pypi.org/project/biotope/) [![Docs](https://github.com/biocypher/biotope/actions/workflows/docs_mkdocs.yaml/badge.svg)](https://biocypher.github.io/biotope/) |
| Meta    | [![Apache 2.0](https://img.shields.io/pypi/l/biotope.svg)](LICENSE) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)                                                                                                         |

> **Pre-alpha.** CLI flags and APIs will change. The plugin skills are the most stable onboarding path.

## Install the plugin

Pick your agent harness. All paths use this repo: [github.com/biocypher/biotope](https://github.com/biocypher/biotope).

| Harness | Setup |
| ------- | ----- |
| **Claude Code** | `/plugin marketplace add biocypher/biotope` then `/plugin install biotope@biotope` |
| **Cursor** | [Add a team marketplace](https://cursor.com/docs/plugins#add-a-team-marketplace) → import `biocypher/biotope` |
| **Codex** | [Add a marketplace from the CLI](https://developers.openai.com/codex/plugins/build#add-a-marketplace-from-the-cli) pointing at this repo |

## Use it

The plugin ships three skills that chain as the pipeline progresses:

| Skill | Use when |
| ----- | -------- |
| **biotope-croissant** | Turning data files into a knowledge graph (`init` → `add` → `map` → `build`) |
| **biocypher** | Tuning export backends, schema config, Neo4j import |
| **biochatter** | Natural-language queries over a loaded graph |

You do not need to learn the CLI first. In chat, invoke a skill (e.g. `/biotope-croissant`) or just ask:

> *What does biotope do? I want to build a graph from my data.*

The agent reads the skill contract and runs `biotope` commands for you.

**Worked example:** [15-minute tutorial](https://biocypher.github.io/biotope/tutorial/) — build a real airport/flight knowledge graph end to end.

**Reference:** [biocypher.github.io/biotope](https://biocypher.github.io/biotope/)

## CLI (manual / scripting)

If you prefer the terminal or need CI:

```bash
uvx biotope init my-kg    # no install — ephemeral venv for scaffolding
pipx install biotope      # global install
uv add biotope              # inside a uv-managed project
```

Typical flow: `init` → `add` (or `get`) → `map` → `build` → `view`. Full command reference lives in the [docs](https://biocypher.github.io/biotope/).

## For developers

biotope is a CLI for the [BioCypher](https://biocypher.org/) ecosystem: Croissant-described data → BioCypher knowledge graph, with git-like metadata version control.

| Layer | Module | Role |
| ----- | ------ | ---- |
| Project & VCS | `biotope.commands.*` | `init`, `add`, `commit`, `status`, `log`, `push`, `pull` — metadata workflow |
| KG construction | `biotope.croissant.*` | Croissant → BioCypher project (`map`, `build`, `alignment`, …) |

Agent contract lives in `skills/` (not `AGENTS.md`). `biotope.croissant.api` exposes pure functions; CLI verbs are thin wrappers. See [architecture](https://biocypher.github.io/biotope/architecture/) and [API docs](https://biocypher.github.io/biotope/api-docs/init/).

```bash
uv sync --extra dev
uv run pytest
uv run ruff check biotope tests
```

## Copyright

Copyright © 2025–2026 BioCypher Team. [Apache 2.0](./LICENSE).
