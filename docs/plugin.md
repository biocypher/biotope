# Plugin and skills

The biotope plugin teaches coding agents how to describe data and author mappings. The agent uses the same `biotope` CLI as a human; no separate agent
API or MCP server is involved.

## Install

=== "Claude Code"

````
```text
/plugin marketplace add biocypher/biotope
/plugin install biotope@biotope
```
````

=== "Cursor"

```
[Add a team marketplace](https://cursor.com/docs/plugins#add-a-team-marketplace)
and import `biocypher/biotope`.
```

=== "Codex"

```
[Add a marketplace from the CLI](https://developers.openai.com/codex/plugins/build#add-a-marketplace-from-the-cli)
using `https://github.com/biocypher/biotope`.
```

To install skills without the plugin, copy the folders you need from
[`skills/`](https://github.com/biocypher/biotope/tree/main/skills) into your
agent's skills directory, such as `.cursor/skills/` or `.claude/skills/`.

## Choose a skill

| Skill               | Use it for                                                |
| ------------------- | --------------------------------------------------------- |
| `biotope-croissant` | Describe data and author mappings: `init` → `add` → `map` |
| `biocypher`         | Configure export backends, schemas, and Neo4j import      |
| `biochatter`        | Query a loaded graph in natural language                  |

Start with `biotope-croissant`. This iteration stops at mapping. The other skills
are for separately managed downstream work.

## Work with the agent

Invoke `/biotope-croissant` to load the skill, or just describe the goal and
let the agent trigger it:

> Turn the CSVs in `data/` into a knowledge graph of genes and diseases.

The skill drives the CLI for you. During a typical session:

1. The agent asks what the graph should answer and which entities and relations
   matter. It records your answers as the project purpose instead of guessing
   from file shapes.
1. It brings your data into the project and runs `add`, which creates a
   Croissant manifest for each dataset.
1. It writes mappings against declared fields and checks their structure.
1. It reports mappings, unresolved decisions and baker limitations. No source
   values, transformations or graph results are validated.

The agent asks about missing purpose or schema decisions and unresolved
scientific choices. It reuses choices already supplied by the user.

Graph construction, export and querying are outside the supported Biotope workflow.

To write mappings yourself, see the [mapping reference](mapping.md). For a full
worked example, follow the [tutorial](tutorial.md).

## Agents without skills

`biotope init --agents-md` adds a project-local `AGENTS.md` fallback. Use it
only when your agent cannot load skills.
