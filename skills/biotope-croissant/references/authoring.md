# Typed authoring

`graph/README.md` in the workspace covers the scaffold itself: the `_example` patterns, source generation semantics, `display_name`, the `--graph` flag and the two-step normalizer. This file covers what the type checker and the runtime require. Do not restate one in the other.

## Every file has one owner

| Location                                     | Responsibility                                                 |
| -------------------------------------------- | -------------------------------------------------------------- |
| `.biotope/datasets/`                         | Managed description; lives outside the graph workspace         |
| `graph/sources/<m>/<record-set>/schema.py`   | Generated source dataclass and its Croissant field references  |
| `graph/sources/<m>/<record-set>/__init__.py` | Authored `SOURCE` registration; created when absent            |
| `graph/sources/<m>/<record-set>/loader.py`   | Authored physical decoding; stub created when absent           |
| `graph/sources/<m>/__init__.py`              | Generated `CONTRACTS` inventory for one manifest               |
| `graph/sources/__init__.py`                  | Authored, selected `SOURCES`                                   |
| `graph/topology/<concept>/`                  | Node dataclass, identifier type, outgoing relation modules     |
| `graph/topology/__init__.py`                 | `TOPOLOGY` registry                                            |
| `graph/mappings/`                            | Typed transformation functions and `MAPPINGS`                  |
| `graph/query_context.py`                     | `QUERY_CONTEXT`: what the graph answers and how to read it     |
| `graph/checks.py`                            | `VALIDATION_CHECKS`: proof that it does                        |
| `graph/pipelines/build_graph.py`             | `PIPELINE`, importing those registries and composing execution |
| `graph/pyproject.toml`                       | Graph dependencies, including project reader libraries         |
| `graph/build/<run>/`                         | Run directory: export files and run evidence                   |

Use `PROJECT_ROOT` from the workspace's `paths` module for existing inputs and managed descriptions, and `GRAPH_ROOT` for graph artifacts. Use package-relative imports. Keep payload access inside loader and pipeline calls.

## Import the contracts from `biotope.graph`

- `SourceContract(name, metadata, generated, records)` links a managed description, its generated module and the participating record classes.
- `Evidence(artifact, version, record_set, location)` identifies a contributor. `SourceRecord(value, evidence)` carries a typed value and its references.
- `Loader[Config, Row]` takes explicit configuration and yields source records. Implement it beside the generated classes with an established parsing library; Biotope ships no source-format readers.
- `Topology(nodes=(...), edges=(...))` registers dataclasses. Each declares `schema_id: ClassVar[str]`. Nodes have distinct `NewType(..., str)` identifiers; edges use those types for `source` and `target`.

Use keyword arguments in graph constructors so a property change fails clearly. Mint namespaced identifiers explicitly, with source-specific namespaces wherever cross-source identity is unresolved. Reuse one concept for same-type relation endpoints rather than inventing a second.

## Describe a property where you declare it

```python
@dataclass(frozen=True)
class Measurement:
    """One reported measurement, retained under the project's admission rule."""

    schema_id: ClassVar[str] = "study:measurement"
    id: MeasurementId
    effect: float = described("Log2 fold change, treated over control; the source's sign, not normalized.")
    note: str | None = described("Free-text source comment, absent for most rows.", default=None)
```

`described(...)` is `dataclasses.field` carrying the text. Descriptions are collected separately from `Topology.describe()`, so improving the wording does not change the topology digest. They reach `query_context.json`, which is the only place a consumer can read them.

## Generated fields are nullable until curation says otherwise

Curated `biotope:nullable: false` asserts non-nullability. Known scalars, nested records and repeated fields are supported; unknown types and `arrayShape` fields become `UnknownValue`. Refine that metadata before loading non-null values; an unused nullable opaque field can stay `None`. `Row.__field_refs__` maps attribute names to Croissant field IDs. Extraction rules and descriptions stay in the Croissant file registered by `SOURCE.metadata`; do not copy them into Python.

Export supports nullable scalars and string lists without nulls or `|`. Any other property shape needs an explicit project representation.

## A mapping's signature is its whole contract

```python
def normalise_sample(sample: SourceRecord[Samples]) -> Iterator[Measurement]:
    row = sample.value
    yield Measurement(sample_id=row.sample_id, tissue=row.tissue.lower())


NORMALISE = Mapping(name="p:normalise-sample", function=normalise_sample, evidence=("Rationale.",))
```

- Every parameter is an explicitly named `SourceRecord[...]`, read through `.value`, so contributors travel with the value. No `*args`, `**kwargs`, defaults or missing annotations.
- Input and output types are concrete dataclasses or finite unions of them. Returns are parameterized `Iterable`, `Iterator`, `Generator`, list or tuple, including a fixed tuple of several output types.
- `Any`, `object`, bare containers and unresolved annotations are rejected at the mapping boundary. Keep the scientific rationale in `evidence`.

## Compose execution through `RunContext`

`Pipeline(name, topology, sources, mappings, run, scope, code_paths, ...)` declares composition. Optional fields include `settings`, `policies`, `intent`, `requirements`, `deferrals`, `dependencies`, `variability`, `query_context` and `validation_checks`. Register the modules holding the last two in `code_paths`. Its `run` receives a `RunContext`:

- `context.load(contract, loader, config)` invokes a registered loader and validates its records without coercion.
- `context.apply(mapping, *records, **keywords)` checks the call against the mapping's signature and returns typed, evidence-bearing outputs.
- `context.map(mapping, *records, **keywords)` makes the same checks and collects graph objects. It accepts only mappings whose outputs declare a `schema_id`.
- `context.exclude(policy_key, evidence, count=1)` records an excluded record against a declared pipeline policy.
- `context.record_audit(stage, inputs=..., outputs=..., selection=..., counts=...)` records one stage's grains, its admission rule and named non-negative counts. Stage names are unique and nothing derives totals from the counts, so name whatever a reader needs to spot a silent drop.
- `context.view()` borrows the collected objects as a `GraphView`; `view.records(Concept)` iterates one declared type without copying the graph.

## Buffer the typed intermediate, never untyped pairs

A `list[SourceRecord[Measurement]]` keeps its element type, so the later `context.map` stays checked. A buffer of untyped mapping and record pairs has to be recovered with casts and checks nothing.

## Joins and conflicts are project Python

Declare keys, cardinality, unmatched behaviour and output grain. Exact duplicates combine evidence; conflicting values for one ID fail the build. Edges without an explicit ID use concept, source and target identity, so parallel edges need explicit IDs. The engine holds graph objects and evidence in memory and project joins may hold more; assess that against the agreed scope.

## Requirement keys repeat the intent text exactly

Keys are `entity:<exact intent text>` or `relation:<exact intent text>`; values are topology concept IDs. Deferrals use the same keys with a reason as the value. A missing binding or deferral fails the definition check. A deferral records a limitation; it does not resolve one.
