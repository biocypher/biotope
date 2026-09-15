# Typed authoring

`graph/README.md` covers the scaffold layout and workflow. This reference describes the type and runtime contracts.

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
| `graph/checks.py`                            | `VALIDATION_CHECKS`: checks of the declared capabilities       |
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
    effect: float = field(
        metadata={"description": "Log2 fold change, treated over control; the source's sign, not normalized."}
    )
    note: str | None = field(default=None, metadata={"description": "Free-text source comment."})
```

Use `dataclasses.field` rather than a wrapper: a helper returning a value makes a required property look defaulted to the type checker, so a missing argument is only caught at run time. Descriptions are collected separately from `Topology.describe()`, so improving the wording does not change the topology digest. They reach `query_context.json` and the exported `BiotopeQueryContext` system rows.

## Generated fields are nullable until curation says otherwise

Curated `biotope:nullable: false` asserts non-nullability. Known scalars, nested records and repeated fields are supported; unknown types and `arrayShape` fields are opaque and nullable by default (`UnknownValue | None`). Refine that metadata before loading non-null values; an unused nullable opaque field can stay `None`. `Row.__field_refs__` maps attribute names to Croissant field IDs. Extraction rules and descriptions stay in the Croissant file registered by `SOURCE.metadata`; do not copy them into Python.

Export supports nullable scalars and string lists without nulls or `|`. Any other property shape needs an explicit project representation.

## Mapping signatures

For source and intermediate dataclasses defined by the project, with non-null
`sample_id` and `tissue` fields, the transformation can have this shape:

```python
def normalise_sample(sample: SourceRecord[Samples]) -> Iterator[NormalizedSample]:
    row = sample.value
    yield NormalizedSample(sample_id=row.sample_id, tissue=row.tissue.lower())


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
- `context.record_audit(stage, inputs=..., outputs=..., selection=..., counts=...)` records one stage's grains, its admission rule and named non-negative counts. Stage names are unique and counts are project-defined, so name them by the source and population they measure.
- `context.view()` builds an isolated `GraphView` for a validation check. Everything it hands out is a copy — `view.concepts`, `view.records(Concept)`, `view.evidence(id)`, `view.mappings(id)` — so a check cannot alter what the run exports or reports.

## Preserve types while buffering

A `list[SourceRecord[Measurement]]` keeps its element type, so the later `context.map` stays checked. Untyped buffers lose this static information and may require casts at later calls.

## Joins and conflicts are project Python

Declare keys, cardinality, unmatched behaviour and output grain. Exact duplicates combine evidence; conflicting values for one ID fail the build. Edges without an explicit ID use concept, source and target identity, so parallel edges need explicit IDs. The engine holds graph objects and evidence in memory and project joins may hold more; assess that against the agreed scope.

## Requirement keys repeat the intent text exactly

Keys are `entity:<exact intent text>` or `relation:<exact intent text>`; values are topology concept IDs. Deferrals use the same keys with a reason as the value. A missing binding or deferral fails the definition check. A deferral records a limitation; it does not resolve one.
