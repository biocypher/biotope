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

Keep raw data and managed metadata at the project level, and graph code under
`graph/`; [project layout](project.md) lists every place biotope writes. Use
`PROJECT_ROOT` and `GRAPH_ROOT` from `graph/paths.py` and package-relative imports
for portability.

| Artifact                                         | Ownership and purpose                                              |
| ------------------------------------------------ | ------------------------------------------------------------------ |
| `<dataset>/.biotope.yaml`, `<file>.biotope.yaml` | What people write about a dataset; its annotation file             |
| `.biotope/datasets/<manifest>.jsonld`            | Description: the data with its annotation file over it             |
| `.biotope/contracts/`                            | Recorded contract revisions, written by `source generate`          |
| `graph/standardization.py`                       | Shared terms that fields of several sources bind to                |
| `graph/sources/<manifest>/__init__.py`           | Generated root collecting that manifest's packages                 |
| `graph/sources/<manifest>/<source>/schema.py`    | Record class and field bindings; scaffolded once, then authored    |
| `graph/sources/<manifest>/<source>/__init__.py`  | `SOURCE` registration, created when absent                         |
| `graph/sources/<manifest>/<source>/loader.py`    | Authored physical reader, created as a placeholder when absent     |
| `graph/sources/inventory.py`                     | Generated `INVENTORY` of every source package                      |
| `graph/sources/__init__.py`                      | Authored `SOURCES` selection and reasoned `EXCLUDED_SOURCES`       |
| `graph/alignment/`                               | Cross-source identity resolution, run before mappings              |
| `graph/extraction/<kind>.py`                     | Extraction schemas, checked with the rest of the graph code        |
| `graph/topology/<node>/node.py`                  | A node dataclass; its folder also holds one file per outgoing edge |
| `graph/mappings/<concept>/`                      | Typed transformations, collected in `MAPPINGS`                     |
| `graph/pipelines/`                               | `compose.py` stage sequence; `build_graph.py` `PIPELINE`           |
| `graph/build/`, `graph/metagraph.html`           | The current build and topology viewer; derived output              |

For earlier projects, see [migration](migration.md).

## Describe and inventory the sources

Use `biotope add <path>` to describe selected local data, then
`biotope map inspect <manifest>` to review the resulting metadata. These operations
have different access requirements: baking reads source bytes; inspection reads
metadata only.

Write what you know about a dataset, such as its licence, table and column
descriptions, keys and equivalent properties, into its
[annotation file](project.md#the-annotation-file), by hand or with
`biotope annotate set`. The description in `.biotope/datasets/` is the data with
that file over it; never edit it by hand. Then generate the sources:

```bash
biotope annotate set data/study --table 'samples.csv#samples' --column raw_score description="Assay score as measured."
biotope source generate .biotope/datasets/data/study.jsonld --out graph/sources
```

Files and tables keep IDs from their paths in the dataset, such as
`samples.csv#samples`, so `biotope add --rebake` after new data changes no ID and
keeps every annotation; see [file and table IDs](project.md#file-and-table-ids).
Baker gives a file it cannot parse, such as a paper or notes, a file entry without
tables; it still becomes a source. Extract a document's records with
[extraction](extraction.md), which registers them as a dataset of their own.

Generation gives every top-level record set, and every file that no record set
reads, its own package. It creates missing files only and never rewrites an
existing schema, registration or loader; only `biotope mv` changes them. The
generated inventory collects every package; in `graph/sources/__init__.py`, select
each source or list it in `EXCLUDED_SOURCES` with a reason. `biotope graph check`
reports a source that is neither, a selected placeholder loader and a described
input without a package. See
[generation details](mapping_sidenotes.md#source-generation) for naming,
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
    __record_set__: ClassVar[str] = "samples.csv#samples"
    __source_digest__: ClassVar[str] = "232b7860…"
    __missing_values__: ClassVar[frozenset[str]] = frozenset({"", "na"})

    sample_id: str                                  # binds samples.csv#samples/sample_id
    score: float = source_field("raw_score", term=SCORE)
    tissue: str | None = source_field(None, default=None)  # not supplied here
```

### Review source drift

`__source_digest__` records the contract revision you reviewed. A revision covers
structure only: fields, types, nullability, keys and file references, not
descriptions or equivalent properties. When the structure changes,
`biotope graph check` reports `source.drift` for each affected schema, with a
field-level summary and every JSON-pointer difference against the recorded
revision. Review the change against the schema and loader, update them, then set
`__source_digest__` to the revision the finding names. Unaffected sources stay
current. `biotope source generate` records each revision it sees; `--check` writes
nothing.

## Define topology and identity

Each node has a folder under `graph/topology/`, named after its class in
snake_case: the node in `node.py`, and one file per edge whose source is that node,
named after the edge class. `Sample` goes in `topology/sample/node.py`, and
`FromPerson`, from a sample to a person, in `topology/sample/from_person.py`.
`biotope graph check` fails with `topology.layout`, naming the class, when a node
or edge sits elsewhere. Other modules there, such as helpers and shared types, are
free. Register the classes in `topology/__init__.py`.

Use frozen dataclasses with stable `schema_id` values. Give each node identifier
its own `NewType` over `str`, and use those types for relation endpoints:

```python
# graph/topology/person/node.py
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
concept IDs. The `biotope:` namespace is reserved for system metadata, and the
export reserves the property names `preferred_id` and `biotope_provenance_id`:
`graph check` reports a property with either name as `topology.reserved` before any
build.

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
implemented. Source validation performs no coercion and applies no declared alias
or missing-value token, so loaders must handle missing tokens, aliases, number
parsing and source-specific representations. Loaders preserve rows:
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
