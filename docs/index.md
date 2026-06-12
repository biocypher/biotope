# biotope

CLI for the BioCypher ecosystem. Turns Croissant-described data into a BioCypher knowledge graph; tracks the metadata in a git-like workflow.

!!! warning "Pre-alpha, developer-facing"

```
APIs, CLI flags, and config-file layouts will change. End-user docs come after the design stabilises.
```

## Quick start: from `init` to a knowledge graph

1. Run `uvx biotope init` or use any other way to make the package available (e.g., `pip install`).

1. Enter desired project name (e.g., `my-kg`) and the overall purpose of the KG (e.g.,
   `Which approved drugs target proteins with relevance in type 2 diabetes?`).

1. Enter directory (`cd my-kg`).

1. Start your coding agent. The `AGENTS.md` file in the directory will onboard it.
   For more information on the process, read on.

## Quick start: without coding agent

!!! tip "Prefer a worked end-to-end example?"

```
The [**Tutorial**](tutorial.md) walks through building a real knowledge graph
from public airport/flight data in ~15 minutes. It's the most up-to-date
onboarding path and the source of truth for the recommended workflow
(`init` → `get` → `add` → `queue` → `map` → `build`).
```

```bash
uv pip install biotope

# 1. Scaffold a project.
biotope init my-kg --purpose "Find approved drugs that target proteins relevant in T2D."
cd my-kg

# 2. Declare what the graph must contain (agent-friendly flags).
biotope map --entity gene --entity disease --entity drug \
            --relation gene_associated_with_disease

# 3. Bring in data + its Croissant metadata.
biotope add data/ot.parquet --license CC-BY-4.0

# 4. Generate an unresolved mapping scaffold for that Croissant file.
#    The scaffold has one slot per declared entity/relation plus an inspector
#    appendix listing record sets, field kinds, and sample rows.
biotope map scaffold .biotope/datasets/ot.jsonld

# 5. Resolve the slots — pick a record set, fields, transforms for each entity
#    and relation. Two equivalent paths:
biotope map                   # interactive guided wizard (humans)
# …or edit mappings/*.mapping.yaml directly and consult:
biotope map inspect .biotope/datasets/ot.jsonld --json
biotope map preview --json    # status + projected schema + sample tuples

# 6. Build a runnable BioCypher project. Strict: rejects unresolved slots.
biotope build
biotope view
```

All semantic decisions (which record set, which fields, which transforms) are made by the human or copilot agent. biotope only enumerates options, validates, and previews — it never auto-picks a "best" record set.

## Commands

### Project lifecycle

- `biotope init` — scaffold a project (`.biotope/`, `AGENTS.md`, `project.yaml`, `git init`).

### Data acquisition + tracking

- `biotope get <source>` — universal ingress verb: copy/download a local file, directory, or URL into the project (or `--crawl` a website) and bake its manifest, recording `dct:source` + a fetch timestamp. Lands under `--into` (default `data`); `--no-add` skips tracking.
- `biotope add <path>` — register data **already in the tree** (e.g. derived artifacts); baker writes the Croissant entry under `.biotope/datasets/`. `--derived-from` records provenance for human/agent-extracted derivatives. For curated metadata that doesn't fit as CLI flags (descriptions, citations, per–record-set fields), `add` also drops a `.biotope.yaml` scaffold next to the dataset — review it, then run `biotope annotate apply <dir>` to merge it into the manifest.
- `biotope mv` / `biotope rm` — move or untrack files and update metadata paths.
- `biotope queue` — show every dataset grouped by pipeline state (`raw` / `processed` / `mapped`). The recommended dashboard during a build.
- `biotope mark <dataset> <status>` — manually set a dataset's `biotope:status`.

### Semantic mapping

- `biotope map` — bare command. If any intent flag (`--purpose`, `--entity`, `--relation`, `--source`, `--notes`, `--clear-*`, `--show`) is passed, it updates `project.yaml` non-interactively. Otherwise it launches the guided wizard.
- `biotope map inspect <croissant>` — deterministic field catalogue + sample rows. `--json` for agents.
- `biotope map scaffold <croissant>` — emit an unresolved mapping scaffold with an inspector comment appendix.
- `biotope map preview [<mapping>]` — validate a (partial) mapping; show projected BioCypher schema + sample tuples. `--json` for agents.
- `biotope propose-alignment` — propose cross-mapping `same_node` equivalences.

### Git-like metadata VCS

- `biotope status` — show staged/modified files and validation state.
- `biotope commit` — commit metadata changes.
- `biotope log` — show metadata commit history.
- `biotope push` / `biotope pull` — sync metadata with a remote.
- `biotope check-data` — verify data files against recorded checksums.

### Knowledge-graph construction

- `biotope build` — materialise a runnable BioCypher project from mappings + alignment. Emits `config/schema_config.yaml` (with `namespace` and autogenerated `input_label`) and per-mapping generated Python under `build/generated/<stem>/`.
- `biotope view` — node/edge counts for the most recent build (or project competence questions if no build yet).

### Annotation + project config

- `biotope annotate` — `apply` (merge a curated `.biotope.yaml` scaffold into a dataset's Croissant manifest, with optional `--set dataset.<field>=…` / `--set record_set.<field>=…` overrides), `edit` (interactive annotation), `load` (sample records via the manifest), `validate` (mlcroissant validation).
- `biotope config` — manage project-level validation rules, remote validation URLs, and project metadata.

### Stubs / not yet wired

- `biotope discover` — rank registered adapters and local Croissant files against `required_entities`. Exists as a CLI entry but the registry surface is not yet wired into the recommended workflow; the tutorial does not use it.
- `biotope benchmark` — quality/coverage metrics. v1 stub: emits a skeleton JSON object so downstream tooling can structure-test against it. Real metric implementations land iteratively.
- `biotope read` — NLP ingestion + health-check entry. Promise.
- `biotope chat` — provider-agnostic conversational interface (biochatter backend). Promise.
- `biotope search` — registry search across MCP / biotools. Auxiliary; not used in the standard build path.

### Deprecated

- `biotope describe` — removed; folded into `biotope map` intent flags.
- `biotope propose-mapping` — deprecated alias for `biotope map scaffold`. The old heuristic ("one RecordSet per node type, FK fields as edges") is gone; the alias now produces an unresolved scaffold for human/agent completion.

## Reading order

1. [Tutorial](tutorial.md) — 15-minute end-to-end walk-through; the ground-truth onboarding path.
1. [Architecture](architecture.md) — modules, data flow, config files.
1. [Project context](project-context.md) — project layout and `.biotope/` files.
1. [Commands](api-docs/init.md) — per-command reference, generated from docstrings.

## Repo

[github.com/biocypher/biotope](https://github.com/biocypher/biotope) · [discussions](https://github.com/orgs/biocypher/discussions/9)
