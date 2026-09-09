# Graph workspace

Run commands from the parent project directory in its Biotope environment.
Keep raw data, existing purpose and managed `.biotope/datasets/` there;
keep graph code, dependencies, notes and outputs inside `graph/`.
`paths.py` supplies `PROJECT_ROOT` for inputs and `GRAPH_ROOT` for graph artifacts.
Use package-relative imports or imports beginning with `graph.`.

## Generate source types

Review the selected Croissant metadata, then generate its Python contract:

```bash
biotope source generate .biotope/datasets/raw.jsonld --out graph/sources/raw/schema.py
```

This reads metadata only. It generates `schema.py` and creates a sibling
`__init__.py` containing `SOURCE` and an unimplemented `loader.py` when absent.
The generated `RECORDS` inventory covers top-level record sets; `SourceRow` is
their type union for the loader. No class-name transcription is needed.

Regenerate `schema.py` when metadata changes; do not edit or format it. Existing
registration and loader files remain authored and are preserved. Review new
record sets and opaque fields before using them. Add the selected `SOURCE` to
`SOURCES` in `graph/sources/__init__.py`; selection remains a project decision.

Generated classes contain typed fields and references to their Croissant IDs
in `__field_refs__` (JSON pointers for fields without IDs). Descriptions and
extraction rules stay in the Croissant file registered by `SOURCE.metadata`.

## Author the graph

The `_example` files illustrate one source row mapping to two nodes and a relation.
They are unregistered, describe no project data, and contain no working reader.
Adapt the patterns below to the research purpose, then remove unused examples.

| Example                                                      | Adaptation                                                                                                                      |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `sources/_example/schema.py`                                 | Inspect this generated contract; generate actual source classes as above.                                                       |
| `sources/_example/loader.py`                                 | Implement physical decoding with an established format library; return typed records with artifact version and record location. |
| `sources/_example/__init__.py`                               | Review the `SOURCE` registration created by generation; narrow its records only when the selected scope requires it.            |
| `topology/_example_record/`, `topology/_example_collection/` | Define node dataclasses, distinct ID NewTypes and outgoing relations with typed endpoints.                                      |
| `mappings/_example.py`                                       | Define identity, null handling and transformations using typed source fields; keep file access in loaders.                      |
| `pipelines/_example.py`                                      | Wire explicit loader configuration through `context.load` and `context.map`; adapt joins and policies for the selected scope.   |

Register the actual definitions in `TOPOLOGY`, `SOURCES` and `MAPPINGS` in their
folders' `__init__.py` files. Complete `pipelines/build_graph.py`: name, selected
scope, requirement bindings or deferrals, policies and execution. Imports must
remain free of payload access and execution. Record loader dependencies in
`pyproject.toml`. The active pipeline rejects its empty name/scope and raises
until implemented; filling placeholders is not scientific validation.

## Check and build

```bash
biotope graph check graph.pipelines.build_graph:PIPELINE --json
# When graph construction is requested:
biotope graph build graph.pipelines.build_graph:PIPELINE --out graph/build/review-1
```

Checks inspect definitions and Python types without invoking loaders. Builds
read selected data and use Biotope's BioCypher exporter, included in
`biotope[graph]`. It derives the export schema from topology and writes graph
files, provenance and `run.json` under the chosen new run directory. No
project-specific BioCypher adapter or separate hand-written export schema is needed.

Checks warn about missing intent, unstated purpose or requirements, and registered
`example:` concepts. Resolve those warnings for research use; the illustrative
example deliberately retains its `example:` namespace.

Review the resulting research graph manually against its purpose and source
evidence. During cleanup, archive or remove run directories under `graph/build/`;
preserve raw data, metadata and authored code.
