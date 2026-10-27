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

Copy the example to a temporary project and initialize it:

```bash
example=$(mktemp -d)
cp -R examples/typed_graph/. "$example/"
cd "$example"
biotope init . --no-prompt
```

Initialization writes `.biotope/` and a root `.gitignore`; it runs no git command.
The example supplies a completed `graph/` workspace, a Croissant description of its
two CSV files written by hand in `metadata/study.jsonld`, and a `project.yaml` with
its purpose, which its pipeline names as its intent. In a new project,
`biotope add` describes the data and `biotope graph scaffold` creates an empty
layout to complete.

## Register and generate sources

The description covers both CSV record sets. Because it is written by hand rather
than baked from the data, `source register` registers it:

```bash
biotope source register metadata/study.jsonld --name study
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
biotope map inspect .biotope/datasets/study.jsonld
```

The example already contains a package per record set,
`graph/sources/study/people/` and `graph/sources/study/samples/`, so generation
reports both as current and writes nothing except their contract revisions in
`.biotope/contracts/`. In a new project it would scaffold each package: a
`schema.py` to edit, a `SOURCE` registration and a placeholder loader. It never
rewrites an existing schema, registration or loader.

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

No bake regenerates a description written by hand, so registering it again is how
it changes. Change the score's declared type in `metadata/study.jsonld` from
`sc:Float` to `sc:Integer`, register the edited description in place of the old
one, and reconcile the sources:

```bash
rm .biotope/datasets/study.jsonld
biotope source register metadata/study.jsonld --name study
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
biotope status
biotope graph check
```

Generation reports `graph/sources/study/samples` as drifted and does not rewrite
the schema; people stays current. `biotope status` marks `study` as changed. The
check fails with `source.drift` for `study/samples`, naming the change:

```text
field samples/score: dataType "sc:Float" -> "sc:Integer"
changed /recordSet/0/field/3/dataType: "sc:Float" -> "sc:Integer"
```

Review what the change means for the schema, the loader and the mappings. Here the
loader keeps parsing the score as a float, so only the acknowledgement remains:
set `__source_digest__` in `graph/sources/study/samples/schema.py` to the revision
the finding names, then run `biotope graph check` again. It passes.

In a project whose data `biotope add` describes, the same drift follows a new
column or a changed column type in the data after `biotope add --rebake`, or a key
in the dataset's annotation file. Descriptions and equivalent properties change no
revision; see [project layout](project.md#source-revisions-cover-structure).

The temporary project can be retained for experimentation. `graph/build/` and
`graph/metagraph.html` are derived outputs; keep `.biotope/`, with its
descriptions and contract history, and the authored code to reproduce a run.
