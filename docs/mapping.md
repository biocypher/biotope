# Typed graph projects

Croissant describes sources; Python defines the graph, its loaders and its
transformations. Biotope generates source records, checks the definitions and
exports validated graph objects through BioCypher. Start with the runnable
[tutorial](tutorial.md) or use this guide to author a project.

## Create the workspace

Install `biotope[graph]` using the [installation guide](installation.md), then run
from your project root:

```bash
biotope graph scaffold
```

This creates `graph/` with registration modules, path constants, dependencies and
inactive examples. Adapt them to the project's purpose before running a build.
Scaffolding works independently of `init` and `add`; it refuses an existing
`graph/` directory or symlink.

Keep raw data, purpose files and managed metadata at the project level. Place
source corrections and graph-specific code under `graph/`. Use `PROJECT_ROOT` and
`GRAPH_ROOT` from `graph/paths.py` and package-relative imports for portability.

| Artifact                                            | Ownership and purpose                                           |
| --------------------------------------------------- | --------------------------------------------------------------- |
| `.biotope/datasets/<manifest>.jsonld`               | Effective source description, reviewed by the project           |
| `graph/sources/<manifest>/__init__.py`              | Generated `CONTRACTS` inventory                                 |
| `graph/sources/<manifest>/<record-set>/schema.py`   | Generated record class; regenerate after metadata changes       |
| `graph/sources/<manifest>/<record-set>/__init__.py` | Authored `SOURCE` registration, created when absent             |
| `graph/sources/<manifest>/<record-set>/loader.py`   | Authored physical reader, created as a stub when absent         |
| `graph/sources/__init__.py`                         | Authored `SOURCES` selection                                    |
| `graph/topology/`                                   | Node and relation dataclasses, collected in `TOPOLOGY`          |
| `graph/mappings/`                                   | Typed transformations, collected in `MAPPINGS`                  |
| `graph/pipelines/build_graph.py`                    | The active `PIPELINE`: selection, joins, policies and execution |
| `graph/query_context.py`, `graph/checks.py`         | Interpretation guidance and declared validation checks          |
| `graph/build/<run>/`, `graph/reports/`              | Derived output and assessments                                  |

For earlier YAML projects, see [migration to 0.9](migration.md).

## Review and generate source records

Use `biotope add <path>` to describe selected local data, then
`biotope map inspect <manifest>` to review the resulting metadata. These operations
have different access requirements: baking reads source bytes; inspection reads
metadata only.

Write evidence-based corrections in a separate Croissant file and register the
complete description:

```bash
biotope source register graph/metadata/study.jsonld --name study \
  --reason "Reviewed source headers and field types"
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
```

Use `--replace` when replacing an existing description. Registration reports
removed keys and identifiers but does not merge documents or judge the review
reason. Reconcile annotations and structural changes before replacement.

Curated or annotated manifests are protected from `add --rebake` and `add --force`.
To refresh one, bake separately and review the differences:

```bash
biotope add raw/study --bake-to graph/metadata/study-fresh.jsonld
# Reconcile this file with the existing curated description before registering it.
biotope source register graph/metadata/study-fresh.jsonld --name study \
  --reason "Reconciled new data with reviewed metadata" --replace
```

Here `study` must be the name of the managed description being replaced.
`--bake-to` takes one input and a new output outside that input and
`.biotope/datasets/`. It does not update tracking. Source locations in the fresh
description retain their original data root.

Generation creates one package per top-level record set. Each schema contains a
record dataclass, its `RECORDS` tuple and `SourceRow` alias. It creates missing
loaders and registrations, preserves existing authored files, and updates the
manifest's `CONTRACTS` inventory. Select the contracts used by the pipeline in
`SOURCES`; generation does not select them for you.

Known scalar, nested and repeated types become Python declarations. Fields are
nullable unless curated metadata asserts otherwise. Unknown types and arrays
remain opaque and need further interpretation before loading. Use
`biotope source generate <manifest> --out graph/sources --check` to check freshness.
See [generation details](mapping_sidenotes.md#source-generation) for naming,
nullability, digests and removed record sets.

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

Concept docstrings and property descriptions appear in the exported query context.
Optional `display_name: ClassVar[str]` values provide short diagram labels without
changing concept IDs. The `biotope:` namespace is reserved for system metadata.

Graph properties support strings, booleans, integers, finite floats, nullable
scalars and string lists. Lists cannot contain nulls or the export separator `|`.
Convert richer source values deliberately in the mappings.

## Implement loaders and mappings

A loader returns `Iterable[SourceRecord[Row]]`. Each record carries a typed value
and `Evidence(artifact, version, record_set, location)`. Use a checksum or known
release version where available; label unverified fingerprints honestly.

Read and decode files inside loader functions using established libraries.
Source validation performs no coercion, so loaders must handle missing tokens,
number parsing and source-specific representations. Include the source location
in decoding errors.

Mapping parameters are named `SourceRecord[...]` values, accessed through `.value`.
The return annotation declares the output dataclasses. `Mapping(name=..., function=...)` registers the function, with optional requirements and evidence.
See `graph/mappings/_example.py` in the scaffold for an implementation.

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

Register `SOURCES`, `TOPOLOGY` and `MAPPINGS`, then complete the `Pipeline` in
`pipelines/build_graph.py`. Include source selection, scope, settings, code paths
and execution. Bind purpose requirements with `entity:<exact intent text>` or
`relation:<exact intent text>` keys, or record a reason in `deferrals`.

Imports must contain declarations only. Source access and execution belong inside
explicitly called functions. Biotope imports project Python; this is an authoring
contract, not an execution sandbox.

## State what the graph can answer

Declare a `QueryContext` in `graph/query_context.py` with:

- `Interpretation` rules for selection, statistics, identity, qualifiers and uncertainty;
- `Capability` entries naming supported question families and their limits;
- `QueryExample` entries when a concrete query helps consumers.

Interpretations reference a concept ID or `<concept ID>.<property>`. Alternatives
must also refer to concepts or properties present in the graph. If another reading
requires excluded rows, state it as a capability limitation.

For example, a graph filtered to `strict_p < 0.05` can describe measurements that
passed that selection. It cannot identify all measurements passing another
adjustment merely because the retained rows also contain an `open_p` column.

Declare `ValidationCheck` functions in `graph/checks.py` to compare claims with
independent expectations from sources, published results or curated answers. Each
receives a `GraphView` and recorded audits, and returns a `ValidationResult`:

| Result         | Effect                                        |
| -------------- | --------------------------------------------- |
| `ok(...)`      | The declared check passed.                    |
| `wrong(...)`   | Validation fails and export is blocked.       |
| `unknown(...)` | The associated capability remains unresolved. |

A check that raises fails the run. With no declared checks, validation is reported
as `absent`. A capability is `supported` only in the sense that its bound checks
passed. Include missing and unexpected records when comparing expected IDs with
observed IDs; use the same declared namespace in both sets.

Definition checks assess declarations. Built-in integrity and quality checks
assess emitted objects. Source-derived expectations are needed to detect records
that should have been emitted but were omitted.

## Check, execute and review

Run from the project root:

```bash
biotope graph check
biotope graph metagraph
biotope graph build --out graph/build/review-1
```

`graph check` checks definitions, source freshness, bindings and Python types
without invoking loaders. `graph metagraph` imports topology independently and
writes an offline viewer. `graph build` checks and executes the pipeline once,
validates the graph and writes a new output directory.

Use `biotope graph quality` when you want to execute and assess without exporting.
Running quality and build separately executes the pipeline twice. Counts,
connectivity and missing-property observations are advisory; execution, integrity
and declared validation failures can block a build.

Review `run.json`, `provenance.jsonl`, `query_context.json` and exported values.
`topology.json` maps concept IDs to export labels, such as `example:sample` to
`ExampleSample` in Biotope 0.9. Query guidance also appears under the exported
`BiotopeQueryContext` system label, outside domain population counts.

Use `biotope graph metagraph --report graph/build/review-1/run.json` to add build
observations to the viewer. See [technical notes](mapping_sidenotes.md) for report
limits, source attribution, reproducibility and export formats.
