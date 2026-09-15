# Graph workspace

This workspace contains declarations and inactive examples to adapt to your
research purpose. Complete the topology, sources, mappings and pipeline before
building. The `_example` files are outside the active registries and contain no
working data reader.

## Environment and paths

Install the published `biotope[graph]>=0.9,<0.10` package in the project environment.
Its croissant-baker dependency comes from PyPI. Pyright needs Node.js on `PATH` or
`pyright[nodejs]`. Record additional reader libraries in `graph/pyproject.toml`.
See [installation](https://biocypher.github.io/biotope/installation/) for setup commands.

Run Biotope commands from the parent project directory. Keep raw data, purpose
files and managed `.biotope/datasets/` there. Keep graph code, corrections, helper
tools and outputs in this workspace. `paths.py` supplies `PROJECT_ROOT` and
`GRAPH_ROOT`; use package-relative imports so the workspace can be renamed.

## Generate source records

Review and register source metadata, then generate its contracts:

```bash
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
```

Replace `study.jsonld` with the managed description you reviewed. Each top-level
record set gets a package under `sources/study/` containing a generated `schema.py`,
a `SOURCE` registration and a loader stub. Generation preserves existing authored
registrations and loaders. The generated manifest-level `CONTRACTS` inventory
collects the packages; select the contracts used by the pipeline in `SOURCES`.

Regenerate after metadata changes and review the diff. Do not edit generated
schemas or inventories. Removed record sets leave orphan packages for you to
review; generation never deletes authored loaders.

## Author the graph

| Location                                    | What to implement                                                            |
| ------------------------------------------- | ---------------------------------------------------------------------------- |
| `sources/<manifest>/<record-set>/loader.py` | Physical decoding and source evidence using established format libraries     |
| `topology/<concept>/`                       | Frozen node and relation dataclasses, stable concept IDs and typed endpoints |
| `mappings/`                                 | Transformations of named `SourceRecord[...]` inputs, read through `.value`   |
| `pipelines/build_graph.py`                  | Scope, source selection, joins, exclusions and execution                     |
| `query_context.py`                          | Supported questions, interpretation rules and limitations                    |
| `checks.py`                                 | Validation against independently established expectations                    |

Use a distinct identifier `NewType` for each node type and mint namespaced IDs.
Describe concepts in class docstrings and properties with
`field(metadata={"description": "..."})`. Optional `display_name` declarations
provide short diagram labels.

Mappings may return topology objects directly. The `_example` files show a
normalization step returning an intermediate dataclass, followed by graph
construction. Use that split when transformations are reused or need buffering.

Register definitions in `TOPOLOGY`, `SOURCES` and `MAPPINGS`, then import those
registries into the active pipeline. `context.load` validates loaded records;
`context.apply` passes typed intermediates onward; `context.map` collects graph
objects. Keep payload access inside explicitly called functions, never imports.

Declare join keys, cardinality, unmatched policies and output grain. Report
excluded records through `context.exclude`, and record stage rules and named
counts through `context.record_audit`. Validation checks can compare the result
with source-derived expectations, including records omitted by the pipeline.

## Check and build

```bash
biotope graph check
biotope graph metagraph
biotope graph build --out graph/build/review-1
```

Check imports declarations and runs type checks without invoking loaders.
Metagraph loads topology independently and writes `reports/metagraph.html`.
Build checks and executes the pipeline, validates its objects and exports a new
run directory. To execute without exporting, use `biotope graph quality` instead.
Running quality and build separately executes twice.

`ValidationResult.wrong` blocks export; `.unknown` leaves the associated capability
unresolved. With no declared checks, validation is `absent`. Built-in quality
warnings describe the emitted graph and need scientific interpretation.

## Review output

Read exported values alongside `run.json`, `provenance.jsonl` and
`query_context.json`. Biotope derives the BioCypher schema from your topology; no
separate project adapter is needed. The query context is also exported under the
`BiotopeQueryContext` system label, outside domain population counts.

Use `biotope graph metagraph --report graph/build/review-1/run.json` to view build
observations. Archive run directories and generated reports when needed, retaining
raw data, curated metadata and authored code for reproduction.

Further reference: [typed graph guide](https://biocypher.github.io/biotope/mapping/),
[technical notes](https://biocypher.github.io/biotope/mapping_sidenotes/), and
[tutorial](https://biocypher.github.io/biotope/tutorial/).
