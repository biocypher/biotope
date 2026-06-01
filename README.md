# biotope

|         |                                                                                                                                                                                                                                                                                                                                              |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Package | [![Latest PyPI Version](https://img.shields.io/pypi/v/biotope.svg)](https://pypi.org/project/biotope/) [![Python](https://img.shields.io/pypi/pyversions/biotope.svg)](https://pypi.org/project/biotope/) [![Docs](https://github.com/biocypher/biotope/actions/workflows/docs_mkdocs.yaml/badge.svg)](https://biocypher.github.io/biotope/) |
| Meta    | [![Apache 2.0](https://img.shields.io/pypi/l/biotope.svg)](LICENSE) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)                                                                                                         |

CLI for the BioCypher ecosystem: Croissant-described data → BioCypher knowledge graph, with git-like metadata version control.

**Status: pre-alpha, developer-facing.** APIs and CLI will change. Not yet suitable for end users.

## Start here

The fastest way in is the **[tutorial](https://biocypher.github.io/biotope/tutorial/)**
— a 15-minute end-to-end walk-through that builds a real knowledge graph from
public airport/flight data. It is the canonical, most up-to-date onboarding
path; the snippet below is just a flavour preview.

## Install

```bash
uv add biotope                     # in a uv-managed venv
pipx install biotope               # global install
uvx biotope init my-kg             # no install: ephemeral venv for the scaffolder
uv pip install -e ".[dev]"         # editable, with test deps (for biotope itself)
```

## From `init` to a knowledge graph

```bash
# 1. Scaffold a project (uvx works fine here — no local install needed).
uvx biotope init my-kg --purpose "What approved drugs target genes in T2D?" --no-prompt
cd my-kg && uv sync

# 2. Bring in data — `biotope get` is the universal ingress verb: copy or
#    download a local file, directory, or URL into the project (or `--crawl` a
#    site) and bake its manifest in one shot, recording where it came from.
#    `biotope add` registers data already in the tree (e.g. derived artifacts).
uv run biotope get https://example.org/opentargets.parquet --into data/ot --license CC-BY-4.0

# 3. Inspect the pipeline state at any time.
uv run biotope queue        # raw / processed / mapped, with provenance footer

# 4. Declare intent — what entities and relations the graph must contain.
#    Non-interactive (agent-friendly); without flags, `biotope map` opens
#    a wizard that captures intent and resolves slots in one flow.
uv run biotope map --entity gene --entity disease --entity drug \
                   --relation gene_associated_with_disease

# 5. Resolve the slots. Two equivalent paths:
#    a) Wizard (humans):  uv run biotope map
#    b) Edit mappings/*.mapping.yaml directly, then validate (agents):
#       uv run biotope map scaffold .biotope/datasets/data/ot.jsonld
#       uv run biotope map inspect  <croissant> --json   # field catalogue
#       uv run biotope map preview  --json               # projected schema + tuples

# 6. Build a runnable BioCypher project. Strict: rejects unresolved slots.
uv run biotope build
uv run python build/create_knowledge_graph.py
uv run biotope view
```

`biotope init` is a pure scaffolder. All non-autogeneratable metadata is supplied as CLI flags — by a user or an agent reading `AGENTS.md`. Semantic decisions (which record set, which fields, which transforms) are made by the human or copilot; biotope only enumerates options, validates, and previews.

## Architecture

Two layers, both in this repo:

| Layer           | Module                | Role                                                                                                             |
| --------------- | --------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Project & VCS   | `biotope.commands.*`  | `init`, `add`, `commit`, `status`, `log`, `push`, `pull`, `mv`, `check-data` — git-like metadata workflow        |
| KG construction | `biotope.croissant.*` | `spec`, `codegen`, `acquisition`, `mapping`, `alignment`, `scaffold`, `registry` — Croissant → BioCypher project |

`biotope.croissant.api` exposes `scaffold_mapping`, `propose_alignment`, `materialize`, `discover_sources` as pure functions; the CLI verbs are thin wrappers. The mapping authoring surface lives under `biotope.commands.map` (Click group) and `biotope.commands.map_wizard` (Rich-based guided flow).

The agent surface is `AGENTS.md` (template lives at `biotope/templates/AGENTS.md`, copied into every project by `init`). No MCP server — agents drive the same CLI a human uses.

## Commands

```
init                                project scaffolding
get add mv rm                       acquisition + tracking (baker writes croissants)
queue mark                          pipeline-state dashboard + manual transitions
map (inspect|scaffold|preview)      semantic mapping (intent + wizard + agent path)
propose-alignment                   cross-mapping same_node equivalences
build view                          build + inspect a graph
status commit log push pull         git-like metadata VCS
check-data                          checksum verification
annotate config                     field-level annotation + project config

discover benchmark                  scaffolded but not yet wired into the standard flow
read chat search                    promises / auxiliary
```

`biotope describe` and the heuristic `biotope propose-mapping` were removed/deprecated. Intent capture is now `biotope map --entity ... --relation ...`; scaffolding is `biotope map scaffold`. `propose-mapping` remains as a deprecated alias for the scaffold subcommand.

See `docs/architecture.md` for the data-flow diagram and `docs/api-docs/` for per-command reference.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check biotope tests
```

Build backend is hatchling; lockfile is `uv.lock`. CI runs `uv sync` + `uv run pytest` on Python 3.10 and 3.12.

## Copyright

Copyright © 2025–2026 BioCypher Team. [Apache 2.0](./LICENSE).
