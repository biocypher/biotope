# biotope

|         |                                                                                                                                                              |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Package | [![Latest PyPI Version](https://img.shields.io/pypi/v/biotope.svg)](https://pypi.org/project/biotope/) [![Python](https://img.shields.io/pypi/pyversions/biotope.svg)](https://pypi.org/project/biotope/) [![Docs](https://readthedocs.org/projects/biotope/badge/?version=latest)](https://biotope.readthedocs.io/) |
| Meta    | [![Apache 2.0](https://img.shields.io/pypi/l/biotope.svg)](LICENSE) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) |

CLI for the BioCypher ecosystem: Croissant-described data → BioCypher knowledge graph, with git-like metadata version control.

**Status: pre-alpha, developer-facing.** APIs and CLI will change. Not yet suitable for end users.

## Install

```bash
uv pip install biotope             # or
uv pip install -e ".[dev]"         # editable, with test deps
```

## From `init` to a knowledge graph

```bash
# 1. Scaffold a project.
biotope init my-kg --purpose "What approved drugs target genes in T2D?"
cd my-kg

# 2. Declare intent — what entities and relations the graph must contain.
#    Non-interactive (agent-friendly):
biotope map --entity gene --entity disease --entity drug \
            --relation gene_associated_with_disease

# 3. Bring in data and its Croissant metadata.
biotope add data/opentargets --license CC-BY-4.0 --creator "Open Targets"
biotope annotate apply data/opentargets        # after reviewing data/opentargets/.biotope.yaml

# 4. Generate an unresolved mapping scaffold from your declared intent.
#    The file has one slot per entity/relation plus an inspector appendix
#    listing record sets, field kinds, identifier-like fields, and sample rows.
biotope map scaffold .biotope/datasets/data/opentargets.jsonld

# 5. Resolve the slots. Two equivalent paths:
#    a) Wizard (humans):            biotope map
#    b) Edit `mappings/*.yaml` directly, then validate (agents):
#       biotope map inspect <croissant> --json   # field catalogue
#       biotope map preview --json               # status + projected schema + sample tuples

# 6. Optional: align entities across multiple mappings.
biotope propose-alignment mappings/*.mapping.yaml --out alignment.yaml

# 7. Build a runnable BioCypher project. Strict: rejects unresolved slots.
biotope build
biotope view
```

`biotope init` is a pure scaffolder. All non-autogeneratable metadata is supplied as CLI flags — by a user or an agent reading `AGENTS.md`. Semantic decisions (which record set, which fields, which transforms) are made by the human or copilot; biotope only enumerates options, validates, and previews.

## Architecture

Two layers, both in this repo:

| Layer            | Module                 | Role                                                                    |
| ---------------- | ---------------------- | ----------------------------------------------------------------------- |
| Project & VCS    | `biotope.commands.*`   | `init`, `add`, `commit`, `status`, `log`, `push`, `pull`, `mv`, `check-data` — git-like metadata workflow |
| KG construction  | `biotope.croissant.*`  | `spec`, `codegen`, `acquisition`, `mapping`, `alignment`, `scaffold`, `registry` — Croissant → BioCypher project |

`biotope.croissant.api` exposes `scaffold_mapping`, `propose_alignment`, `materialize`, `discover_sources` as pure functions; the CLI verbs are thin wrappers. The mapping authoring surface lives under `biotope.commands.map` (Click group) and `biotope.commands.map_wizard` (Rich-based guided flow).

The agent surface is `AGENTS.md` (template lives at `biotope/templates/AGENTS.md`, copied into every project by `init`). No MCP server — agents drive the same CLI a human uses.

## Commands

```
init                                project scaffolding
map (inspect|scaffold|preview)      semantic mapping (intent + wizard + agent path)
add mv status commit log push pull  git-like metadata VCS
check-data                          checksum verification
discover                            registry-aware source ranking
propose-alignment                   cross-mapping same_node equivalences
build view benchmark                build + inspect a graph
read chat                           NLP ingestion, conversation (promises)
search annotate get config          legacy / auxiliary
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
