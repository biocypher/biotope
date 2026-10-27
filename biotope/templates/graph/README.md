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
  extraction/            extraction schemas, one <kind>.py per kind of document
  topology/
    __init__.py          TOPOLOGY: the registered nodes and edges
    <node>/              one folder per node, its class name in snake_case
      node.py            the node dataclass
      <edge>.py          one edge whose source is this node, named the same way
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

Run Biotope commands from the parent project directory, where the data, its
annotation files and `.biotope/` live. `paths.py` supplies `PROJECT_ROOT` and
`GRAPH_ROOT`; use package-relative imports. Biotope never writes to git: commit
this workspace with the project. `.gitignore` here keeps `build/` and
`metagraph.html` out.

## Workflow

1. Describe each dataset with `biotope add data/study`, and write what you know
   about it, such as descriptions, keys and a licence, into its annotation file,
   `data/study/.biotope.yaml`. Every input the graph might use must be described,
   documents included. Extract a document's records with `biotope extract run`
   and a schema in `extraction/<kind>.py`.

1. Scaffold its sources:

   ```bash
   biotope source generate .biotope/datasets/data/study.jsonld --out graph/sources
   ```

   Each RecordSet, and each file no RecordSet reads, gets a package named after
   its ID, such as `push_people_csv_people` for `push/people.csv#people`.
   Generation creates missing files only; it never rewrites a schema,
   registration or loader, and only `biotope mv` updates the IDs in them. It
   records every contract revision in `.biotope/contracts/`.

1. Select sources in `sources/__init__.py`. A source that is not used goes into
   `EXCLUDED_SOURCES` with a reason; every inventoried source is one or the other.
   As scaffolded, it selects every source, so a new table in later data fails the
   check until its loader is written. To rebuild after new data without a hand
   edit, select sources by name and exclude the rest with one rule; see
   [project layout](https://biocypher.github.io/biotope/project/).

1. Edit each selected schema: names, types, missing-value tokens and bindings to
   terms in `standardization.py`. Implement its loader, which reads the file at
   `SOURCE.path()`, and delete the loader's `# biotope:placeholder` first line.
   Loaders preserve rows; they do not filter.

1. Declare each node in `topology/<node>/node.py` and each edge in its source
   node's folder, one file per edge: `Sample` in `topology/sample/node.py`, and
   `FromPerson`, from a sample to a person, in `topology/sample/from_person.py`.
   `biotope graph check` enforces this layout; other modules there are free.
   Register them in `topology/__init__.py`. Describe every concept in its
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

After new data of the same shape, refresh with commands only; files and tables
keep IDs from their paths, so no schema, loader or annotation changes:

```bash
biotope add --rebake data/study
biotope source generate .biotope/datasets/data/study.jsonld --out graph/sources
biotope graph check
biotope graph build
```

Move data files with `biotope mv`, which updates every ID that names them. When
the structure changes, such as a new column, a changed type or a key in the
annotation file, `biotope graph check` reports `source.drift` for each affected
schema and explains the change. Review it, update the schema, then set its
`__source_digest__` to the revision the finding names. Descriptions and a file's
changed content never cause drift.

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
