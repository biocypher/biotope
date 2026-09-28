# Graph workspace

This workspace holds the project-owned code that turns described sources into a
typed graph. Scientific preprocessing stays upstream: loaders decode what the
sources report, and mappings select and construct graph objects.

## Layout

```text
graph/
  standardization.py     shared terms that fields of several sources bind to
  sources/
    __init__.py          selected sources and explicit, reasoned exclusions
    inventory.py         generated: every source package, collected on import
    <manifest>/          generated root for one managed Croissant manifest
      <source>/          one package per RecordSet or undescribed file
        __init__.py      SOURCE registration
        schema.py        typed records and field bindings; yours to edit
        loader.py        decoding into the schema; starts as a placeholder
  alignment/             cross-source identity resolution, before mappings
  topology/<concept>/    node dataclasses and their outgoing relations
  mappings/<concept>/    selection, joins and graph-object construction
  pipelines/
    compose.py           the stage sequence
    build_graph.py       registration, scope and scientific policies
  build/                 the current generated graph (not committed)
  metagraph.html         generated topology view
```

## Environment

Install the published `biotope[graph]>=0.10,<0.11` package in the project
environment. Pyright needs Node.js on `PATH` or `pyright[nodejs]`. Record reader
libraries that loaders import, such as pandas, in `graph/pyproject.toml`;
`biotope graph check` warns about an undeclared import, and `run.json` records the
installed version of each. See
[installation](https://biocypher.github.io/biotope/installation/).

Run Biotope commands from the parent project directory, where raw data, the
purpose file and the managed `.biotope/datasets/` live. `paths.py` supplies
`PROJECT_ROOT` and `GRAPH_ROOT`; use package-relative imports.

## Workflow

1. Register each reviewed Croissant description with `biotope source register`.
   Every input the graph might use must be described, documents included.

1. Scaffold its sources:

   ```bash
   biotope source generate .biotope/datasets/study.jsonld --out graph/sources
   ```

   Each RecordSet, and each file no RecordSet reads, gets a package. Generation
   creates missing files only; it never rewrites a schema, registration or
   loader. It records every contract revision in `.biotope/contracts/`.

1. Select sources in `sources/__init__.py`. A source that is not used goes into
   `EXCLUDED_SOURCES` with a reason; every inventoried source is one or the other.

1. Edit each selected schema: names, types, missing-value tokens and bindings to
   terms in `standardization.py`. Implement its loader and delete the loader's
   `# biotope:placeholder` first line. Loaders preserve rows; they do not filter.

1. Declare concepts in `topology/<concept>/`. Describe every concept in its
   docstring and every property with `field(metadata={"description": ...})`;
   the descriptions travel with the export.

1. Resolve identities in `alignment/`, then write mappings and the stage
   sequence in `pipelines/compose.py`. Report excluded records through
   `context.exclude` and stage accounts through `context.record_audit`.

1. Check, build and inspect:

   ```bash
   biotope graph check
   biotope graph build
   biotope graph metagraph --report graph/build/run.json
   ```

When a manifest changes, `biotope graph check` reports `source.drift` for each
affected schema and explains the change. Review it, update the schema, then set
its `__source_digest__` to the revision the finding names.

## Artifacts

A successful build replaces `graph/build/` from staging; a failed rebuild keeps
the previous graph and writes `build/last_failure.json`.

| Artifact                | Purpose                                                                      |
| ----------------------- | ---------------------------------------------------------------------------- |
| `schema_config.yaml`    | Labels, properties, descriptions and constraints                             |
| `biocypher_config.yaml` | Export settings                                                              |
| `run.json`              | Inputs, code fingerprints, settings, bindings, counts, exclusions and checks |
| `provenance.json`       | Shared source and contributor evidence                                       |
| `biocypher/`            | Import data, headers and script                                              |

Every exported node and edge carries `biotope_provenance_id`, an index into
`provenance.json`, so distribute `graph/build/` with the graph. Checks establish
structure, not scientific correctness: review selected records against the
sources themselves before relying on the graph.

Further reference: [typed graph guide](https://biocypher.github.io/biotope/mapping/),
[technical notes](https://biocypher.github.io/biotope/mapping_sidenotes/) and
[tutorial](https://biocypher.github.io/biotope/tutorial/).
