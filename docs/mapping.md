# Typed graph projects

Croissant describes sources; Python defines the graph, its loaders and its
transformations. Biotope inventories every described source, checks the definitions
and exports validated graph objects through BioCypher. Start with the runnable
[tutorial](tutorial.md) or use this guide to author a project.

## Create the workspace

Install `biotope[graph]` using the [installation guide](installation.md), then run
from your project root:

```bash
biotope graph scaffold
```

This creates `graph/` with empty registries, path constants, dependencies, a
generated source inventory and a pipeline to complete; its README describes the
layout. Scaffolding works independently of `init` and `add`; it refuses an existing
`graph/` directory or symlink.

Keep raw data, purpose files and managed metadata at the project level, and graph
code under `graph/`. Use `PROJECT_ROOT` and `GRAPH_ROOT` from `graph/paths.py` and
package-relative imports for portability.

| Artifact                                        | Ownership and purpose                                           |
| ----------------------------------------------- | --------------------------------------------------------------- |
| `.biotope/datasets/<manifest>.jsonld`           | Effective source description, reviewed by the project           |
| `.biotope/contracts/`                           | Recorded contract revisions, written by `source generate`       |
| `graph/standardization.py`                      | Shared terms that fields of several sources bind to             |
| `graph/sources/<manifest>/__init__.py`          | Generated root collecting that manifest's packages              |
| `graph/sources/<manifest>/<source>/schema.py`   | Record class and field bindings; scaffolded once, then authored |
| `graph/sources/<manifest>/<source>/__init__.py` | `SOURCE` registration, created when absent                      |
| `graph/sources/<manifest>/<source>/loader.py`   | Authored physical reader, created as a placeholder when absent  |
| `graph/sources/inventory.py`                    | Generated `INVENTORY` of every source package                   |
| `graph/sources/__init__.py`                     | Authored `SOURCES` selection and reasoned `EXCLUDED_SOURCES`    |
| `graph/alignment/`                              | Cross-source identity resolution, run before mappings           |
| `graph/topology/<concept>/`                     | Node and relation dataclasses, collected in `TOPOLOGY`          |
| `graph/mappings/<concept>/`                     | Typed transformations, collected in `MAPPINGS`                  |
| `graph/pipelines/`                              | `compose.py` stage sequence; `build_graph.py` `PIPELINE`        |
| `graph/build/`, `graph/metagraph.html`          | The current build and topology viewer; derived output           |

For earlier projects, see [migration](migration.md).

## Describe and inventory the sources

Use `biotope add <path>` to describe selected local data, then
`biotope map inspect <manifest>` to review the resulting metadata. These operations
have different access requirements: baking reads source bytes; inspection reads
metadata only.

Write evidence-based corrections in a separate Croissant file under
`.biotope/reviews/` and register the complete description:

```bash
biotope source register .biotope/reviews/study.jsonld --name study \
  --reason "Reviewed source headers and field types"
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
```

Use `--replace` when replacing an existing description. Registration reports
removed keys and identifiers but does not merge documents or judge the review
reason. Reconcile annotations and structural changes before replacement.

Curated or annotated manifests are protected from `add --rebake` and `add --force`.
To refresh one, bake separately and review the differences:

```bash
biotope add raw/study --bake-to .biotope/reviews/study-fresh.jsonld
# Reconcile this file with the existing curated description before registering it.
biotope source register .biotope/reviews/study-fresh.jsonld --name study \
  --reason "Reconciled new data with reviewed metadata" --replace
```

Here `study` must be the name of the managed description being replaced.
`--bake-to` takes one input and a new output outside that input and
`.biotope/datasets/`. It does not update tracking. Source locations in the fresh
description retain their original data root.

Baker leaves files it cannot parse, such as papers and notes, unclaimed. Add a
`FileObject` with a stable `@id`, its `contentUrl` and `sha256` for each such file
the graph may read; it then becomes a source like any table.

Generation gives every top-level record set, and every file that no record set
reads, its own package. It creates missing files only and never rewrites an
existing schema, registration or loader. The generated inventory collects every
package; in `graph/sources/__init__.py`, select each source or list it in
`EXCLUDED_SOURCES` with a reason. `biotope graph check` reports a source that is
neither, a selected placeholder loader and a described input without a package.
See [generation details](mapping_sidenotes.md#source-generation) for naming,
ownership, conflicts and removed sources.

Each schema starts from the description: known scalar, nested and repeated types
become Python declarations, fields are nullable unless curated metadata asserts
otherwise, and unknown types and arrays stay opaque. The schema is then yours to
edit. Bind each Croissant field once with `source_field`, declare source-local
missing-value tokens and aliases, and bind fields to shared terms from
`standardization.py` only where sources share a meaning:

```python
@dataclass(frozen=True, kw_only=True)
class Samples:
    __record_set__: ClassVar[str] = "samples"
    __source_digest__: ClassVar[str] = "232b7860…"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({"", "na"})

    sample_id: str                                  # binds samples/sample_id
    score: float = source_field("raw_score", term=SCORE)
    tissue: str | None = source_field(None, default=None)  # not supplied here
```

### Review source drift

`__source_digest__` records the contract revision you reviewed. When the
description changes, `biotope graph check` reports `source.drift` for each affected
schema, with a field-level summary and every JSON-pointer difference against the
recorded revision. Review the change against the schema and loader, update them,
then set `__source_digest__` to the revision the finding names. Unaffected sources
stay current. `biotope source generate` records each revision it sees; `--check`
writes nothing.

## Define topology and identity

Use frozen dataclasses with stable `schema_id` values. Give each node identifier
its own `NewType` over `str`, and use those types for relation endpoints:

```python
from dataclasses import dataclass, field
from typing import ClassVar, NewType

PersonId = NewType("PersonId", str)

@dataclass(frozen=True)
class Person:
    """One person referenced by at least one selected sample."""

    schema_id: ClassVar[str] = "study:person"
    id: PersonId
    name: str = field(metadata={"description": "Name as recorded by the source."})
```

Mint namespaced IDs such as `study-a:person-17` explicitly. Static ID types prevent
accidental endpoint swaps; they do not establish uniqueness or shared biological
identity. Runtime checks reject conflicting objects with the same ID and resolve
edges against the declared endpoint types.

Concept docstrings and property descriptions are exported in `schema_config.yaml`,
and `graph check` warns about concepts and properties without one. Optional
`display_name: ClassVar[str]` values provide short diagram labels without changing
concept IDs. The `biotope:` namespace is reserved for system metadata.

Graph properties support strings, booleans, integers, finite floats, nullable
scalars and string lists. Lists cannot contain nulls. For the Neo4j import files,
strings are one line and list items contain no `;` or line break; a build stops at
the first graph object that breaks this and names its mapping, concept and
property. Convert richer source values deliberately in the mappings.

## Implement loaders and mappings

A loader returns `Iterable[SourceRecord[Row]]`. Each record carries a typed value
and `Evidence(artifact, version, record_set, location)`. Use a checksum or known
release version where available; label unverified fingerprints honestly.

Read and decode files inside loader functions using established libraries, and
delete the placeholder's `# biotope:placeholder` first line once the loader is
implemented. Source validation performs no coercion, so loaders must handle missing
tokens, number parsing and source-specific representations. Loaders preserve rows:
they do not filter, impute or deduplicate. Include the source location in decoding
errors.

Mapping parameters are named `SourceRecord[...]` values, accessed through `.value`.
The return annotation declares the output dataclasses. `Mapping(name=..., function=...)` registers the function, with optional requirements and evidence.
The [tutorial](tutorial.md) project shows a complete implementation.

A mapping can return topology objects directly. Introduce an intermediate
dataclass when sources need a shared normalized shape, a stage requires buffering,
or several mappings reuse a transformation. Intermediates have no `schema_id`.
Keep file access in loaders and transformations in mappings.

Inside the pipeline:

- `context.load(...)` validates source records as they are read.
- `context.apply(mapping, ...)` returns typed records for another transformation.
- `context.map(mapping, ...)` collects outputs that declare graph identities.
- `context.exclude(...)` records excluded records under a declared policy.
- `context.record_audit(...)` records a stage's grain, selection rule and named counts.

Ordinary Python owns joins, indexes, aggregation and resource lifetimes. State the
join keys, cardinality, unmatched policy and output grain. Account for omitted
records through exclusions or audits. Every graph object enters through a
registered mapping; there is no direct emission API.

Resolve cross-source identity in `graph/alignment/` before any mapping admits a
record: gather every source's identifiers first, so the result does not depend on
read order, and keep each resolution's contributing rows as evidence. Write the
stage sequence in `pipelines/compose.py`, then complete the `Pipeline` in
`pipelines/build_graph.py` with scope, policies, settings and code paths; the
scaffold already wires `SOURCES`, `INVENTORY`, `EXCLUDED_SOURCES` and `TERMS`. Bind purpose requirements with `entity:<exact intent text>` or
`relation:<exact intent text>` keys, or record a reason in `deferrals`.

Imports must contain declarations only. Source access and execution belong inside
explicitly called functions. Biotope imports project Python; this is an authoring
contract, not an execution sandbox.

## Describe what the graph means

The consumer receives the graph and `graph/build/`, not the project. Interpretation
therefore travels in three places: concept and property descriptions in
`schema_config.yaml`, the pipeline's `scope`, and its `policies`, one per exclusion
reported through `context.exclude(...)`. State in them what each value measures,
against which reference, when identifiers can be joined, and what the selection
left out. Record open scientific questions in `graph/ASSUMPTIONS.md`.

Separate selection from query filters. A graph filtered to `strict_p < 0.05` can
describe measurements that passed that selection. It cannot identify all
measurements passing another adjustment merely because the retained rows also
contain an `open_p` column. If two readings need different populations, admit
their union and let the query choose.

Biotope checks structure, not science. Definition checks assess declarations;
integrity and quality checks assess emitted objects. None of them can see a record
that should have been emitted but was not. Before relying on a claim, compare the
graph with expectations read independently from the sources or a published
result, never from the pipeline's own selection, and compare missing and
unexpected records by namespaced ID.

## Check, execute and review

Run from the project root:

```bash
biotope graph check
biotope graph metagraph
biotope graph build
```

`graph check` checks the source inventory, drift, definitions, bindings and Python
types without invoking loaders. `graph metagraph` imports topology independently
and writes `graph/metagraph.html`. `graph build` checks and executes the pipeline
once, validates the graph and replaces `graph/build/` after success; a failed
rebuild keeps the previous build and writes `graph/build/last_failure.json`.

Use `biotope graph quality` when you want to execute and assess without exporting;
it prints the assessment. Running quality and build separately executes the
pipeline twice. Counts, connectivity and missing-property observations are
advisory; definition, execution and integrity failures block a build.

Review `run.json`, `schema_config.yaml`, `provenance.json` and exported values.
Export labels are the concept's local name, such as `Sample` for `example:sample`,
widened only when two concepts collide. Every exported object carries
`biotope_provenance_id`, an index into `provenance.json`.

Use `biotope graph metagraph --report graph/build/run.json` to add build
observations to the viewer. See [technical notes](mapping_sidenotes.md) for report
limits, source attribution, reproducibility and export formats.
