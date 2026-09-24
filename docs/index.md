# Biotope

Biotope turns reviewed descriptions of local data into typed Python graph projects.
You define the research purpose, source readers, identities and transformations;
Biotope checks the definitions and exports BioCypher files with provenance.

## Start here

- [Install Biotope](installation.md) from PyPI, including its published croissant-baker dependency.
- [Run the tutorial](tutorial.md) to build a small graph from synthetic CSV data.
- [Author a graph](mapping.md) from your own curated source descriptions.
- [Set up a coding agent](plugin.md) to use the same workflow with repository skills.

## Workflow

```text
Local data → Croissant metadata → Review → Source inventory
                                                ↓
                  Python schemas, loaders, topology and mappings
                                                ↓
                              Check → Build → Review graph output
```

`biotope add` reads local data and describes it with croissant-baker. Review those
metadata before generating source classes: a successful scan does not establish
that every field or file was described completely.

`biotope graph scaffold` creates a workspace, and `biotope source generate` gives
every described input a source package with a schema to edit. Project Python code
then loads selected data, transforms typed records and constructs the graph. `biotope graph check` checks declarations and types; `biotope graph build`
executes the pipeline, validates its objects and writes the export.

A build records source references, exclusions and the concept and property
descriptions that interpret the graph. Use these to assess whether the graph
supports its intended questions. Structural checks alone cannot establish
scientific validity: review the graph against the sources themselves.

## Reference

- [Commands](commands.md)
- [Architecture](architecture.md)
- [Technical notes for typed graphs](mapping_sidenotes.md)
- [Shared annotation policies](cluster-compliance.md)
- [Migrating to 0.10](migration.md)

Biotope 0.10 supports Python 3.10–3.12. APIs may change while the project is under
active development. Source code and issue reporting are on
[GitHub](https://github.com/biocypher/biotope).
