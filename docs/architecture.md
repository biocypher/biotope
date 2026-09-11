# Architecture

Biotope connects curated source descriptions to typed, project-owned graph
construction. Croissant-baker describes formats. Generated dataclasses describe
source values. Authored Python defines topology, mappings and pipeline composition.
Biotope checks those definitions and integrates validated outputs with BioCypher.

```text
raw sources ── baker ── curated Croissant ── generated source classes
    │                                               │
    └── project loaders ── typed records ── mappings ── graph objects
                                              │           │
                                       Python topology    └── BioCypher files
```

Generation and definition checking read metadata and Python only. Explicit
baking/file-integrity commands and project pipeline execution read source bytes.
Loaders, joins, identity decisions and scientific transformations live in the
graph project. Biotope has no format-reader framework or expression compiler.

Execution runs definition checks, then the exporter environment check, then the
project pipeline, reference integrity, project validation checks, quality
measurement and export, in that order. Validation sits there because everything
above it measures only what the pipeline emitted and therefore cannot see a
record it never emitted; comparing against an expectation from outside the
pipeline is the project's job, and Biotope supplies the interface and the
reporting rather than the expectation. A failed check blocks export; an
unverified one marks its capability unresolved and lets the rest through.
Project descriptions, interpretation rules and run evidence are generated into
one versioned query context that ships with the export, because a consuming
agent receives the graph and nothing else.

`graph scaffold` copies the packaged boilerplate into `graph/`. Initialization,
baking and execution remain separate commands. CLI code owns mechanical setup;
the agent adapts topology, loaders and transformations to purpose and evidence.

The [typed project guide](mapping.md) describes layouts, interfaces, supported
values, provenance, failure behavior and memory assumptions. `biotope.graph`
exports the project contracts; `biotope.graph.sources`, `.check` and `.build`
provide generation, definition checks and explicit execution. `biotope.croissant`
retains metadata models and inspection. `biotope.commands` provides CLI wrappers
and the existing metadata/Git workflow.

## Authority and revisions

Curated Croissant is the source-contract authority. Python topology is the only
target-schema authority. Python functions are the mappings. YAML used for intent,
annotations and derived BioCypher configuration does not define a second graph.
Semantic concept IDs are independent of module names. Regeneration replaces only
generated modules; metadata corrections and authored code survive.

Definitions must be safe to import. Python can have arbitrary side effects, so
Biotope does not claim to sandbox project code or infer its complete lineage.
Runtime validation, static checking and scientific review establish different
things. Passing one does not establish the others.

## Design credit

Paul Ka Po To's `kg-build-system` informed typed authoring, topology organization
and modular construction. Biotope implements these ideas independently using
ordinary Python dataclasses and mapping functions; it does not vendor or depend
on that engine. No code from it was copied. A bounded future contribution can
improve this foundation without gating Biotope's implementation or release.

## Contributor checks

Install the graph and development extras (`uv sync --extra dev --extra graph`)
and make Node.js available on PATH. Run `uv run python -m pyright --version` to
verify the checker installation, then `uv run pyright` and `uv run pytest tests/`. The integration
suite exercises real Pyright and BioCypher; missing dependencies are setup failures,
not skipped acceptance checks. The locked Pyright wheel bundles its JavaScript
checker. Runtime downloads may be needed if Node is missing or its bundled checker
is explicitly overridden.

The current local baker override expects `../croissant-baker`; replacing that
with the published dependency remains the shared release gate.
