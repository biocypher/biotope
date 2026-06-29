# biotope

Turn tables, CSVs, and mixed biomedical data into a queryable knowledge graph — with version-controlled metadata. **Best used with a coding agent:** install the plugin, describe what you want the graph to answer, and let the agent run the pipeline.

!!! warning "Pre-alpha"

    CLI flags and APIs will change. The plugin skills are the most stable onboarding path.

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

**Worked example:** [Tutorial](tutorial.md) — build a real airport/flight knowledge graph in ~15 minutes.

## CLI (manual / scripting)

If you prefer the terminal or need CI:

```bash
uvx biotope init my-kg    # no install — ephemeral venv for scaffolding
pipx install biotope      # global install
uv add biotope              # inside a uv-managed project
```

**Reference:** [Commands](commands.md) overview · [API docs](api-docs/init.md) per-command detail

All semantic decisions (which record set, which fields, which transforms) are made by the human or agent. biotope enumerates options, validates, and previews — it never auto-picks a "best" record set.

## Reading order

1. [Tutorial](tutorial.md) — end-to-end walk-through; ground-truth onboarding path.
1. [Commands](commands.md) — command overview by pipeline stage.
1. [Architecture](architecture.md) — modules, data flow, config files.
1. [Project context](project-context.md) — project layout and `.biotope/` files.
1. [API docs](api-docs/init.md) — per-command reference, generated from docstrings.

## Repo

[github.com/biocypher/biotope](https://github.com/biocypher/biotope) · [discussions](https://github.com/orgs/biocypher/discussions/9)
