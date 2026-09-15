# biotope

Describe local data, define a purpose and target schema, and author mappings
and selected graph pipelines in typed Python, with version-controlled metadata.

!!! warning "Pre-alpha"

```
CLI flags and APIs will change. The plugin skills are the most stable onboarding path.
```

## Start with a coding agent

Install the [biotope plugin](plugin.md), then invoke `/biotope-croissant` or ask:

> What does biotope do? I want to build a graph from my data.

The agent asks what the graph should answer and runs the pipeline:

```text
init → add → graph scaffold → source generate → Python authoring → graph check → graph build
```

Graph authoring starts with `biotope graph scaffold`, which creates `graph/`.
Initialization and baking do not create or execute a graph.

Semantic choices stay with you or your agent. Biotope generates source types, checks definitions, and validates graph output; it never guesses the best record set or field mapping.

## Use the CLI

For manual or scripted use, install Biotope and the updated baker in the same
environment. During this unreleased integration, use editable installs of both
local checkouts. The following options apply to published releases:

=== "Try without installing"

````
```bash
uvx biotope init my-kg
```
````

=== "Install globally"

````
```bash
pipx install "biotope>=0.8.0"
```
````

=== "Add to a uv project"

````
```bash
uv add "biotope>=0.8.0"
```
````

Next:

- [Build the small typed example](tutorial.md).
- Use the [command overview](commands.md) for manual work and scripts.
- Write mappings by hand with the [mapping reference](mapping.md).
- Read [how biotope works](architecture.md) for project layout and data flow.
