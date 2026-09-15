# Build the typed example

This tutorial joins three synthetic samples to two people. It demonstrates source
generation, typed mappings, exclusions, provenance and BioCypher export.

## Set up

Use Python 3.12, [uv](https://docs.astral.sh/uv/getting-started/installation/), Git
and Node.js on `PATH`. Clone the example from the release matching the package:

```bash
git clone --depth 1 --branch biotope-v0.9.0 https://github.com/biocypher/biotope.git biotope-example
cd biotope-example
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python 'biotope[graph]==0.9.0'
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

The example supplies a completed `graph/` workspace and a `project.yaml` with its
purpose. Initialization preserves that file. In a new project,
`biotope graph scaffold` creates the layout with inactive examples to adapt.

## Register and generate sources

The fixture includes reviewed Croissant metadata describing both CSV record sets:

```bash
biotope source register graph/metadata/study.jsonld --name study --reason "Reviewed synthetic fixture-v1"
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
biotope map inspect .biotope/datasets/study.jsonld
```

Generation creates one package per record set: `graph/sources/study/people/` and
`graph/sources/study/samples/`. Each `schema.py` holds a generated dataclass,
`RECORDS` and the `SourceRow` alias. Existing loaders and source registrations
are preserved.

Read these files to follow the transformation:

| File                                    | Role                                                             |
| --------------------------------------- | ---------------------------------------------------------------- |
| `graph/sources/study/samples/schema.py` | Declares the source fields and their types.                      |
| `graph/sources/study/samples/loader.py` | Reads CSV and decodes the score as a float.                      |
| `graph/mappings/samples.py`             | Doubles the score and constructs namespaced graph IDs.           |
| `graph/pipelines/build_graph.py`        | Selects records, joins samples to people and records exclusions. |

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

- Read `run.json` for completion, counts, exclusions, audits and validation.
- Pair each `biocypher/*-header.csv` with its `*-part000.csv` to inspect exported values.
- Use `topology.json` to resolve export labels to concept IDs.
- Read `provenance.jsonl` for source locations and `query_context.json` for interpretation rules.

The export also includes `BiotopeQueryContext` system nodes. These are separate
from the three domain nodes reported above. Compare `graph_digest` in both run
records; it should match despite different output paths and timestamps.

To view the topology with build observations:

```bash
biotope graph metagraph --report graph/build/first/run.json
```

Open `graph/reports/metagraph.html` in a browser. The viewer works offline.

## Change a source contract

Edit a field description in `graph/metadata/study.jsonld`, then register and
generate the revised metadata:

```bash
biotope source register graph/metadata/study.jsonld --name study --reason "Reviewed updated field description" --replace
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
biotope graph check
```

Generation reads the registered description. It updates affected generated
modules and preserves authored loaders and mappings. Changes to types or field
names may require corresponding Python edits.

The temporary project can be retained for experimentation. Build directories and
reports are derived outputs; preserve curated metadata and authored code if you
want to reproduce a run.
