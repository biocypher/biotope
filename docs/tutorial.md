# Build the typed example

This tutorial joins three synthetic samples to two people. It demonstrates the
source inventory, typed mappings, exclusions, provenance, BioCypher export and
source drift.

## Set up

Use Python 3.12, [uv](https://docs.astral.sh/uv/getting-started/installation/), Git
and Node.js on `PATH`. Clone the example from the release matching the package:

```bash
git clone --depth 1 --branch biotope-v0.10.0 https://github.com/biocypher/biotope.git biotope-example
cd biotope-example
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python 'biotope[graph]==0.10.0'
source .venv/bin/activate
```

If Node.js is unavailable, install `pyright[nodejs]` in this environment as
shown in [installation](installation.md).

Copy the example to a temporary project and initialize metadata tracking:

```bash
example=$(mktemp -d)
cp -R examples/typed_graph/. "$example/"
cd "$example"
biotope init . --no-git --no-prompt
```

The example supplies a completed `graph/` workspace, its reviewed Croissant
description in `metadata/study.jsonld` and a `project.yaml` with its purpose.
Initialization preserves that file. In a new project, `biotope graph scaffold`
creates an empty layout to complete.

## Register and generate sources

The fixture's description covers both CSV record sets:

```bash
biotope source register metadata/study.jsonld --name study --reason "Reviewed synthetic fixture-v1"
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
biotope map inspect .biotope/datasets/study.jsonld
```

The example already contains a package per record set,
`graph/sources/study/people/` and `graph/sources/study/samples/`, so generation
reports both as current and writes nothing except their contract revisions in
`.biotope/contracts/`. In a new project it would scaffold each package: a
`schema.py` to edit, a `SOURCE` registration and a placeholder loader. It never
rewrites an existing file.

Read these files to follow the transformation:

| File                                    | Role                                                               |
| --------------------------------------- | ------------------------------------------------------------------ |
| `graph/sources/study/samples/schema.py` | Declares the source fields, their types and the reviewed revision. |
| `graph/sources/study/samples/loader.py` | Reads CSV and decodes the score as a float.                        |
| `graph/sources/__init__.py`             | Selects every source of the inventory; excludes none.              |
| `graph/mappings/sample/__init__.py`     | Doubles the score and constructs namespaced graph IDs.             |
| `graph/pipelines/build_graph.py`        | Joins samples to people and records exclusions.                    |

The `SOURCES`, `TOPOLOGY` and `MAPPINGS` registries select the definitions used by
the pipeline. See the [authoring guide](mapping.md) for the full layout.

## Check and build

```bash
biotope graph check
biotope graph build --out graph/build/first
biotope graph build --out graph/build/second
```

Expect **three domain nodes and two domain edges**: Ada, samples s1 and s2, and
their relations. The sample scores are **3.0 and 5.0**. Checks warn about the
illustrative `example:` namespace.

Sample s3 has no matching person; Bea has no selected sample. Both exclusions
appear in `run.json`. Ada's provenance includes her people row and the two
contributing sample rows.

## Review the result

Inside `graph/build/first/`:

- Read `run.json` for completion, scope, policies, counts, exclusions and audits.
- Read `schema_config.yaml` for each exported label (`Sample`, `Person`, `FromPerson`)
  with its concept ID and the concept and property descriptions.
- Pair each `biocypher/*-header.csv` with its `*-part000.csv` to inspect exported values.
- Follow a row's `biotope_provenance_id` into `provenance.json` for its mappings and
  source locations.

Compare `graph_digest` in both run records; it should match despite different
output paths and timestamps. Without `--out`, `biotope graph build` writes
`graph/build/` and replaces it on the next successful build. It refuses a
`graph/build/` that holds other directories, such as the two builds above, so
delete them first.

To view the topology with build observations:

```bash
biotope graph metagraph --report graph/build/first/run.json
```

Open `graph/metagraph.html` in a browser. The viewer works offline.

## Change a source contract

Change the score's declared type in `metadata/study.jsonld` from `sc:Float` to
`sc:Integer`, then register the revised description and reconcile the sources:

```bash
biotope source register metadata/study.jsonld --name study --reason "Score reviewed as an integer" --replace
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
biotope graph check
```

Generation reports `graph/sources/study/samples` as drifted and never rewrites the
schema; people stays current. The check fails with `source.drift` for
`study/samples`, naming the change:

```text
field samples/score: dataType "sc:Float" -> "sc:Integer"
changed /recordSet/0/field/3/dataType: "sc:Float" -> "sc:Integer"
```

Review what the change means for the schema, the loader and the mappings. Here the
loader keeps parsing the score as a float, so only the acknowledgement remains:
set `__source_digest__` in `graph/sources/study/samples/schema.py` to the revision
the finding names, then run `biotope graph check` again. It passes.

The temporary project can be retained for experimentation. `graph/build/` and
`graph/metagraph.html` are derived outputs; preserve curated metadata, the
`.biotope/contracts/` history and authored code if you want to reproduce a run.
