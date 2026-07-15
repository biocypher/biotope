# biotope

Turn tables, CSVs, and mixed biomedical data into a queryable knowledge graph,
with version-controlled metadata.

!!! warning "Pre-alpha"

    CLI flags and APIs will change. The plugin skills are the most stable onboarding path.

## Start with a coding agent

Install the [biotope plugin](plugin.md), then invoke `/biotope-croissant` or ask:

> What does biotope do? I want to build a graph from my data.

The agent asks what the graph should answer and runs the pipeline:

```text
init → add → map → build → view
```

Semantic choices stay with you or your agent. Biotope inspects, validates, and
previews; it never guesses the best record set or field mapping.

## Use the CLI

For manual or scripted use:

=== "Try without installing"

    ```bash
    uvx biotope init my-kg
    ```

=== "Install globally"

    ```bash
    pipx install "biotope>=0.8.0"
    ```

=== "Add to a uv project"

    ```bash
    uv add "biotope>=0.8.0"
    ```

Next:

- [Build an airport graph](tutorial.md) in about 15 minutes.
- Use the [command overview](commands.md) for manual work and scripts.
- Write mappings by hand with the [mapping reference](mapping.md).
- Read [how biotope works](architecture.md) for project layout and data flow.
