# Plugin and skills

The biotope plugin teaches coding agents how to run the knowledge-graph
pipeline. The agent uses the same `biotope` CLI as a human; no separate agent
API or MCP server is involved.

## Install

=== "Claude Code"

    ```text
    /plugin marketplace add biocypher/biotope
    /plugin install biotope@biotope
    ```

=== "Cursor"

    [Add a team marketplace](https://cursor.com/docs/plugins#add-a-team-marketplace)
    and import `biocypher/biotope`.

=== "Codex"

    [Add a marketplace from the CLI](https://developers.openai.com/codex/plugins/build#add-a-marketplace-from-the-cli)
    using `https://github.com/biocypher/biotope`.

To install skills without the plugin, copy the folders you need from
[`skills/`](https://github.com/biocypher/biotope/tree/main/skills) into your
agent's skills directory, such as `.cursor/skills/` or `.claude/skills/`.

## Choose a skill

| Skill | Use it for |
| --- | --- |
| `biotope-croissant` | Build a graph from data: `init` → `add` → `map` → `build` |
| `biocypher` | Configure export backends, schemas, and Neo4j import |
| `biochatter` | Query a loaded graph in natural language |

Start with `biotope-croissant`. Add the other skills when the pipeline reaches
those stages.

## Work with the agent

Invoke `/biotope-croissant` to load the skill, or just describe the goal and
let the agent trigger it:

> Turn the CSVs in `data/` into a knowledge graph of genes and diseases.

The skill drives the CLI for you. During a typical session:

1. The agent asks what the graph should answer and which entities and relations
   matter. It records your answers as the project purpose instead of guessing
   from file shapes.
2. It brings your data into the project and runs `add`, which creates a
   Croissant manifest for each dataset.
3. It writes one mapping per dataset and previews each edit. A clean preview
   does not guarantee a connected graph, so this may take several passes.
4. It builds the graph and checks node counts, edge counts, and orphaned edges
   before reporting success.

The agent asks before choosing the graph's purpose, extracting facts from
unstructured files, selecting `csv` or `neo4j`, or changing the declared
schema.

When the pipeline reaches export tuning or querying, the agent switches to the
matching skill: `biocypher` for Neo4j import and schema config, `biochatter`
for natural-language queries.

To write mappings yourself, see the [mapping reference](mapping.md). For a full
worked example, follow the [tutorial](tutorial.md).

## Agents without skills

`biotope init --agents-md` adds a project-local `AGENTS.md` fallback. Use it
only when your agent cannot load skills.
