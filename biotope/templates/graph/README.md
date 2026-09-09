# Graph workspace

Run commands from the parent project directory in its Biotope environment.
Keep raw data, existing purpose and managed `.biotope/datasets/` there;
keep graph code, dependencies, notes and outputs inside `graph/`.
`paths.py` supplies `PROJECT_ROOT` for inputs and `GRAPH_ROOT` for graph artifacts.
Use package-relative imports so the workspace can be renamed. All graph commands
accept `--graph <folder>`; project inputs remain relative to its parent.

## Generate source types

Review the selected Croissant metadata, then generate its Python contract:

```bash
biotope source generate .biotope/datasets/raw.jsonld --out graph/sources
```

This reads metadata only. **One record set becomes one source package.** Every
top-level record set of the manifest gets `graph/sources/raw/<record-set>/`,
holding a generated `schema.py` with a single record class, plus a sibling
`__init__.py` containing `SOURCE` and an unimplemented `loader.py` when absent.
`RECORDS` holds that one class and `SourceRow` aliases it. No class-name
transcription is needed. Folder and class names follow the record set `@id`.

Because each package covers one record set, adding, removing or re-encoding one
upstream file touches one folder. Regenerate when metadata changes; do not edit
or format generated files. Existing registration and loader files remain authored
and are preserved. A record set removed from the manifest leaves an orphaned
package: it is reported, never deleted, and removing it is your decision.

`graph/sources/raw/__init__.py` is generated and exports `CONTRACTS`, every
package's `SOURCE`. Review new record sets and opaque fields, then add the
selected contracts to `SOURCES` in `graph/sources/__init__.py`; selection remains
a project decision.

Generated classes contain typed fields and references to their Croissant IDs
in `__field_refs__` (a reference under the record set's identity for fields
without IDs). Descriptions and
extraction rules stay in the Croissant file registered by `SOURCE.metadata`.

## Author the graph

The `_example` files illustrate one source row mapping to two nodes and a relation.
They are unregistered, describe no project data, and contain no working reader.
Adapt the patterns below to the research purpose, then remove unused examples.

| Example                                                      | Adaptation                                                                                                                      |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `sources/_example/example_rows/schema.py`                    | Inspect this generated contract; generate actual source classes as above.                                                       |
| `sources/_example/example_rows/loader.py`                    | Implement physical decoding with an established format library; return typed records with artifact version and record location. |
| `sources/_example/example_rows/__init__.py`                  | Review the `SOURCE` registration created by generation.                                                                         |
| `sources/_example/__init__.py`                               | Generated `CONTRACTS` inventory; select from it rather than editing it.                                                         |
| `topology/_example_record/`, `topology/_example_collection/` | Define node dataclasses, distinct ID NewTypes and outgoing relations with typed endpoints.                                      |
| `mappings/_example.py`                                       | Define identity, null handling and transformations using typed source fields; keep file access in loaders.                      |
| `pipelines/_example.py`                                      | Wire explicit loader configuration through `context.load` and `context.map`; adapt joins and policies for the selected scope.   |

Each node/relation may declare `display_name: ClassVar[str]` for a short diagram
label, alongside its stable `schema_id`. Choose readable names such as "Sample"
or "Measured in". The fallback is the Python class name split into words. Labels
do not alter identity or exported data; full IDs remain in viewer details and JSON.

Register the actual definitions in `TOPOLOGY`, `SOURCES` and `MAPPINGS` in their
folders' `__init__.py` files. Complete `pipelines/build_graph.py`: name, selected
scope, requirement bindings or deferrals, policies and execution. Imports must
remain free of payload access and execution. Record loader dependencies in
`pyproject.toml`. The active pipeline rejects its empty name/scope and raises
until implemented; filling placeholders is not scientific validation.

## Check, inspect and execute

```bash
biotope graph check --json
biotope graph metagraph
# To execute and assess without export:
biotope graph quality --json
# When graph construction is requested:
biotope graph build --out graph/build/review-1
```

Checks inspect definitions and Python types without invoking loaders. Metagraph
reads `TOPOLOGY` independently and writes offline `reports/metagraph.html`.
Quality executes loaders and mappings, checks graph objects, and saves
`reports/quality.json` without export. It reports counts, missing properties,
connectivity, endpoint concentration and self-loops. Warnings need interpretation;
failed execution leaves measurements unrun. Running quality and build separately
executes twice; choose only what is needed.

Builds
read selected data and use Biotope's BioCypher exporter, included in
`biotope[graph]`. It derives the export schema from topology and writes graph
files, provenance and `run.json` under the chosen new run directory. No
project-specific BioCypher adapter or separate hand-written export schema is needed.

Checks warn about missing intent, unstated purpose or requirements, and registered
`example:` concepts. Resolve those warnings for research use; the illustrative
example deliberately retains its `example:` namespace.

Use `graph metagraph --report graph/reports/quality.json` (or a build `run.json`)
for matching-topology observations. JSON mode writes no HTML; old reports without
measurements stay unmeasured.

Review the resulting research graph manually against its purpose and source
evidence. During cleanup, archive or remove run directories under `graph/build/`;
generated reports under `graph/reports/` can also be regenerated. Preserve raw
data, metadata and authored code.
