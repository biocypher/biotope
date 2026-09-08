# biotope

Describe local data, define a purpose and target schema, and author mappings
with version-controlled metadata. This iteration stops at mapping.

!!! warning "Pre-alpha"

```
CLI flags and APIs will change. The plugin skills are the most stable onboarding path.
```

## Start with a coding agent

Install the [biotope plugin](plugin.md), then invoke `/biotope-croissant` or ask:

> What does biotope do? I want to build a graph from my data.

The agent asks what the graph should answer and runs the pipeline:

```text
init → add → map inspect/scaffold/preview
```

Semantic choices stay with you or your agent. Biotope inspects, validates, and
summarizes mapping definitions; it never guesses the best record set or field mapping.

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

- [Map a small local gene table](tutorial.md).
- Use the [command overview](commands.md) for manual work and scripts.
- Write mappings by hand with the [mapping reference](mapping.md).
- Read [how biotope works](architecture.md) for project layout and data flow.
