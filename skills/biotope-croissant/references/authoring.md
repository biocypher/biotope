# Typed authoring

`graph/README.md` covers the scaffold layout and workflow. This reference describes the type and runtime contracts.

## Contents

- Every file has one owner: the workspace layout
- Import the contracts from `biotope.graph`
- Describe a property where you declare it
- A schema is scaffolded once, then authored: bindings, encodings, drift
- Mapping signatures
- Compose execution through `RunContext`
- Preserve types while buffering
- Joins and conflicts are project Python
- Requirement keys repeat the intent text exactly

## Every file has one owner

| Location                                 | Responsibility                                                       |
| ---------------------------------------- | -------------------------------------------------------------------- |
| `.biotope/datasets/`                     | Managed description; lives outside the graph workspace               |
| `.biotope/contracts/`                    | Recorded contract revisions; written by `biotope source generate`    |
| `graph/standardization.py`               | Shared `Term`s that fields of several sources bind to                |
| `graph/sources/<m>/<source>/schema.py`   | Authored record dataclass and its field bindings; scaffolded once    |
| `graph/sources/<m>/<source>/__init__.py` | `SOURCE` registration; created when absent                           |
| `graph/sources/<m>/<source>/loader.py`   | Authored decoding; a placeholder until implemented                   |
| `graph/sources/<m>/__init__.py`          | Generated root: collects the packages of one manifest                |
| `graph/sources/inventory.py`             | Generated `INVENTORY` of every root                                  |
| `graph/sources/__init__.py`              | Authored `SOURCES` and reasoned `EXCLUDED_SOURCES`                   |
| `graph/alignment/`                       | Cross-source identity resolution, run before mappings                |
| `graph/topology/<concept>/`              | Node dataclass, identifier type, outgoing relation modules           |
| `graph/mappings/<concept>/`              | Typed transformation functions; `MAPPINGS` in `mappings/__init__.py` |
| `graph/pipelines/compose.py`             | The stage sequence: load, align, map                                 |
| `graph/pipelines/build_graph.py`         | `PIPELINE`: registries, scope, policies and settings                 |
| `graph/ASSUMPTIONS.md`                   | Open scientific questions and the interpretations they affect        |
| `graph/pyproject.toml`                   | Graph dependencies, including project reader libraries               |
| `graph/build/`                           | The current build: export files and run evidence; generated          |

Use `PROJECT_ROOT` from the workspace's `paths` module for existing inputs and manifests, and `GRAPH_ROOT` for graph artifacts. Use package-relative imports. Keep payload access inside loader and pipeline calls.

## Import the contracts from `biotope.graph`

- `SourceContract(name, metadata, schema, records)` links a manifest, the source's schema module and its record classes. Generation writes it; keep the registration as generated, apart from its import when you rename the record class.
- `Evidence(artifact, version, record_set, location)` identifies a contributor. `SourceRecord(value, evidence)` carries a typed value and its references.
- `Loader[Config, Row]` takes explicit configuration and yields source records. Implement it beside the schema with an established parsing library; Biotope ships no source-format readers.
- `Term(standard_name, description, values=None)` and `source_field(...)` bind source fields to shared meanings.
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

Use `dataclasses.field` rather than a wrapper: a helper returning a value makes a required property look defaulted to the type checker, so a missing argument is only caught at run time. Descriptions are collected separately from `Topology.describe()`, so improving the wording does not change the topology digest. They reach `schema_config.yaml` as `description` and `biotope.property_descriptions`; `graph check` reports concepts and properties without one.

## A schema is scaffolded once, then authored

`biotope source generate` writes each `schema.py` once and never rewrites it. Its types, nesting and nullability start from the manifest: curated `biotope:nullable: false` asserts non-nullability; known scalars, nested records and repeated fields are supported; unknown types and `arrayShape` fields are opaque and nullable (`UnknownValue | None`). Refine that metadata before loading non-null values; an unused nullable opaque field can stay `None`. Extraction rules and descriptions stay in the Croissant file; do not copy them into Python.

Every described field is bound exactly once:

```python
@dataclass(frozen=True, kw_only=True)
class Row:
    __record_set__: ClassVar[str] = "de_table"
    __source_digest__: ClassVar[str] = "<revision>"
    # Source-local policy: these tokens are missing values, case-insensitively.
    __missing_values__: ClassVar[frozenset[str]] = frozenset({"", "na", "nan"})

    gene_symbol: str = source_field("Gene", term=GENE_SYMBOL)
    log_fold_change: float = source_field("logFC", term=LOG_FOLD_CHANGE)
    cell_type: str  # binds de_table/cell_type by its own name
    gene_accession: str | None = source_field(None, default=None)  # not supplied by this source
```

- `source_field("<suffix>")` names the field `<record set @id>/<suffix>`; a bare attribute binds its own name; a full `@id` works when the suffix is empty or itself scoped; `source_field(None)` declares an attribute the source does not supply.
- Aliases (`aliases={"low": "low_expression"}`), missing tokens and species context belong to the source that uses them. A `Term` holds only the meaning, and optionally the closed vocabulary, several sources share. A field bound to a term is an attribute named after the term's `standard_name`. Bind every field the graph reads as that meaning; matching column names establish no equivalence, and a field kept as its source reported it needs no term.
- Authored types are not compared with Croissant `dataType`. `__source_digest__` records the revision you reviewed; when the manifest changes, `graph check` reports `source.drift` with the changes, and you acknowledge them by updating it.
- A 0.9 schema with `__field_refs__` still binds; it cannot be combined with `source_field` metadata.

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
- Every value is validated against its declaration when the mapping runs, so a field of an intermediate or source record is `str`, `int`, `float`, `bool`, `None`, a `NewType`, `list[...]`, `tuple[...]` or a dataclass. The check rejects other field types, such as `dict` or `set`, before a build starts.

## Compose execution through `RunContext`

`Pipeline(name, topology, sources, mappings, run, scope, code_paths, ...)` declares composition. Optional fields include `settings`, `policies`, `intent`, `requirements`, `deferrals`, `dependencies`, `variability`, `terms`, `source_inventory` and `excluded_sources`; the scaffold wires `terms=TERMS`, `source_inventory=INVENTORY` and `excluded_sources=EXCLUDED_SOURCES`. List `standardization.py`, `alignment`, `sources`, `topology`, `mappings` and `pipelines` in `code_paths`. Its `run` receives a `RunContext`:

- `context.load(contract, loader, config)` invokes a registered loader and validates its records without coercion. A selected source's loader must run to completion during the build.
- `context.apply(mapping, *records, **keywords)` checks the call against the mapping's signature and returns typed, evidence-bearing outputs.
- `context.map(mapping, *records, **keywords)` makes the same checks and collects graph objects. It accepts only mappings whose outputs declare a `schema_id`.
- `context.exclude(policy_key, evidence, count=1)` records an excluded record against a declared pipeline policy.
- `context.record_audit(stage, inputs=..., outputs=..., selection=..., counts=...)` records one stage's grains, its admission rule and named non-negative counts. Stage names are unique and counts are project-defined, so name them by the source and population they measure.

## Preserve types while buffering

A `list[SourceRecord[Measurement]]` keeps its element type, so the later `context.map` stays checked. Untyped buffers lose this static information and may require casts at later calls.

## Joins and conflicts are project Python

Declare keys, cardinality, unmatched behaviour and output grain. Exact duplicates combine evidence; conflicting values for one ID fail the build. Edges without an explicit ID use concept, source and target identity, so parallel edges need explicit IDs. The engine holds graph objects and evidence in memory and project joins may hold more; assess that against the agreed scope.

## Requirement keys repeat the intent text exactly

Keys are `entity:<exact intent text>` or `relation:<exact intent text>`; values are topology concept IDs. Deferrals use the same keys with a reason as the value. A missing binding or deferral fails the definition check. A deferral records a limitation; it does not resolve one.
