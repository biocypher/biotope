# Build the small typed example

The repository's `examples/typed_graph` project joins three synthetic samples to
two people. It exercises generation, typed mappings, exclusions, provenance and
actual BioCypher output. It does not read any consulting data.

## Set up

From the Biotope checkout, install both local packages, including the graph extra:

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -e ../croissant-baker -e '.[graph]'
source .venv/bin/activate
```

Pyright uses Node.js. Keep `node` on your PATH, or install the bundled runtime
once with `uv pip install --python .venv/bin/python 'pyright[nodejs]'` before checking.

Copy the example into a scratch directory, then enter it:

```bash
example=$(mktemp -d)
cp -R examples/typed_graph/. "$example/"
cd "$example"
biotope init . --no-git --no-prompt
```

The example contains a completed `graph/` workspace using the scaffold's registry
convention: `SOURCES`, `TOPOLOGY` and `MAPPINGS` in their folders' `__init__.py`
files feed `pipelines/build_graph.py`. For a new project, `biotope graph scaffold`
creates the same layout with inactive examples and an unimplemented pipeline.

The example already has a visible `project.yaml` containing its purpose.
The pipeline references that file explicitly. Do not replace its contents.

## Generate and inspect

The example supplies reviewed Croissant descriptions so the types are predictable:

```bash
biotope source register graph/metadata/people.jsonld --name people --reason "Reviewed synthetic fixture-v1"
biotope source register graph/metadata/samples.jsonld --name samples --reason "Reviewed synthetic fixture-v1"
biotope source generate .biotope/datasets/people.jsonld --out graph/sources/people/schema.py
biotope source generate .biotope/datasets/samples.jsonld --out graph/sources/samples/schema.py
biotope map inspect .biotope/datasets/samples.jsonld
```

Read `graph/sources/samples/schema.py`, then its sibling `loader.py`. The generated
class contains declarations; `RECORDS` supplies the inventory used by each
source's `SOURCE` registration. Generation preserves the example's authored
registrations and loaders. For a new source, it creates those files when absent.
The loader uses Python's CSV library and explicitly
decodes the score to `float`. `graph/mappings/samples.py` doubles that score and mints
namespaced identifiers. `graph/pipelines/build_graph.py` states the join and exclusions.

## Check and build

```bash
biotope graph check graph.pipelines.build_graph:PIPELINE
biotope graph build graph.pipelines.build_graph:PIPELINE --out graph/build/first
biotope graph build graph.pipelines.build_graph:PIPELINE --out graph/build/second
```

Expect **three nodes and two edges**: Ada, samples s1 and s2, and their relations.
Definition checks warn about the intentionally illustrative `example:` concepts.
The scores are **3.0 and 5.0**. Sample s3 has no person match; Bea has no selected
sample. Both exclusions appear in `run.json`. Ada's provenance has three references:
her people row and both contributing sample rows.

Open `graph/build/first/biocypher/*-header.csv` with the corresponding `*-part000.csv`
to interpret each file. `topology.json` maps export labels to stable concept IDs.
`provenance.jsonl` links IDs back to source locations. Compare the two `graph_digest`
values in `run.json`; they should match.

## Try an edit

In `graph/mappings/samples.py`, rename a source-property access or swap the relation's
endpoint IDs. `graph check` should fail with a useful Pyright diagnostic. Repair
it before building. Change a curated field description, run `source generate`
again, then repair affected loader/mapping code. Authored files are never
regenerated. See [typed projects](mapping.md) for the validation boundaries.

## Clean up

From the scratch project, archive its generated run outputs:

```bash
mkdir -p graph/review-backups
archive=$(mktemp -d "$PWD/graph/review-backups/build-XXXXXX")
for path in graph/build; do
  if [ -d "$path" ]; then mv "$path" "$archive/"; fi
done
echo "$archive"
```

Keep curated metadata, purpose, topology, source modules and mappings for review.
Do not use `biotope rm` to clean up graph outputs.
