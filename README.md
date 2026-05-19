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

## Workflow

```bash
biotope init my-kg --purpose "What approved drugs target genes in T2D?"
cd my-kg
biotope describe --entity gene --entity disease --entity drug \
                 --relation gene_associated_with_disease

biotope add data/ot.parquet --license CC-BY-4.0    # baker fills Croissant fields
biotope propose-mapping .biotope/datasets/ot.jsonld --out mappings/ot.mapping.yaml
biotope propose-alignment mappings/*.mapping.yaml --out alignment.yaml
biotope build
biotope view
```

`biotope init` is a pure scaffolder. All non-autogeneratable metadata is supplied as CLI flags — by a user or an agent reading `AGENTS.md`.

## Architecture

Two layers, both in this repo:

| Layer            | Module                 | Role                                                                    |
| ---------------- | ---------------------- | ----------------------------------------------------------------------- |
| Project & VCS    | `biotope.commands.*`   | `init`, `add`, `commit`, `status`, `log`, `push`, `pull`, `mv`, `check-data` — git-like metadata workflow |
| KG construction  | `biotope.croissant.*`  | `spec`, `codegen`, `acquisition`, `mapping`, `alignment`, `scaffold`, `registry` — Croissant → BioCypher project |

`biotope.croissant.api` exposes `propose_mapping`, `propose_alignment`, `materialize`, `discover_sources` as pure functions; the CLI verbs are thin wrappers.

The agent surface is `AGENTS.md` (template lives at `biotope/templates/AGENTS.md`, copied into every project by `init`). No MCP server — agents drive the same CLI a human uses.

## Commands

```
init describe                       project lifecycle
add mv status commit log push pull  git-like metadata VCS
check-data                          checksum verification
discover                            registry-aware source ranking
propose-mapping propose-alignment   declarative KG configuration
build view benchmark                build + inspect a graph
read chat                           NLP ingestion, conversation (promises)
search annotate get config          legacy / auxiliary
```

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
