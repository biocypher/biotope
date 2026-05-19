# biotope

CLI for the BioCypher ecosystem. Turns Croissant-described data into a BioCypher knowledge graph; tracks the metadata in a git-like workflow.

!!! warning "Pre-alpha, developer-facing"

    APIs, CLI flags, and config-file layouts will change. End-user docs come after the design stabilises.

## Quick start

```bash
uv pip install biotope

biotope init my-kg --purpose "What approved drugs target genes in T2D?"
cd my-kg
biotope describe --entity gene --entity disease --entity drug \
                 --relation gene_associated_with_disease
biotope add data/ot.parquet --license CC-BY-4.0
biotope propose-mapping .biotope/datasets/ot.jsonld --out mappings/ot.mapping.yaml
biotope build
biotope view
```

## Commands

### Project lifecycle

- `biotope init` — scaffold a project (`.biotope/`, `AGENTS.md`, `project.yaml`, `git init`).
- `biotope describe` — set the project's competence questions (`purpose`, `required_entities`, `required_relations`).

### Git-like metadata VCS

- `biotope add` — stage data files; baker enriches the Croissant entry under `.biotope/datasets/`.
- `biotope mv` — move tracked files; updates metadata paths.
- `biotope status` — show staged/modified files and validation state.
- `biotope commit` — commit metadata changes.
- `biotope log` — show metadata commit history.
- `biotope push` / `biotope pull` — sync metadata with a remote.
- `biotope check-data` — verify data files against recorded checksums.

### Knowledge-graph construction

- `biotope discover` — rank registered adapters and local Croissant files against `required_entities`.
- `biotope propose-mapping` — heuristic `mapping.yaml` from a Croissant file.
- `biotope propose-alignment` — propose cross-Croissant same_node equivalences.
- `biotope build` — materialise a runnable BioCypher project from mappings + alignment.
- `biotope view` — node/edge counts for the most recent build.
- `biotope benchmark` — quality/coverage metrics (skeleton in v1).

### Promises (not feature-complete)

- `biotope read` — NLP ingestion + health-check entry.
- `biotope chat` — provider-agnostic conversational interface (biochatter backend ships first).
- `biotope search` / `biotope get` / `biotope annotate` / `biotope config` — auxiliary surfaces.

## Reading order

1. [Architecture](architecture.md) — modules, data flow, config files.
2. [Git integration](git-integration.md) — how metadata version control works.
3. [API docs](api-docs/init.md) — per-command reference, generated from docstrings.

## Repo

[github.com/biocypher/biotope](https://github.com/biocypher/biotope) · [discussions](https://github.com/orgs/biocypher/discussions/9)
