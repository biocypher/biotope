# Typed authoring reference

Read the generated `graph/README.md` for scaffold examples. If a Biotope checkout
is available, `examples/typed_graph/` demonstrates a working two-source join and
`docs/mapping.md` describes the API. This reference supplies the essentials when
the skill is copied into a data project.

## File ownership and registration

| Location                                     | Responsibility                                                     |
| -------------------------------------------- | ------------------------------------------------------------------ |
| `.biotope/datasets/`                         | Effective source metadata, managed outside the graph workspace     |
| `graph/sources/<m>/<record-set>/schema.py`   | Generated source dataclass and references to Croissant fields      |
| `graph/sources/<m>/<record-set>/__init__.py` | Authored `SOURCE` registration; created when absent                |
| `graph/sources/<m>/<record-set>/loader.py`   | Authored physical decoding; unimplemented stub created when absent |
| `graph/sources/<m>/__init__.py`              | Generated `CONTRACTS` inventory of one manifest's packages         |
| `graph/sources/__init__.py`                  | Authored, selected `SOURCES`                                       |
| `graph/topology/<concept>/`                  | Node dataclass, identifier type and outgoing relation modules      |
| `graph/topology/__init__.py`                 | `TOPOLOGY` registry                                                |
| `graph/mappings/`                            | Typed transformation functions and `MAPPINGS` in `__init__.py`     |
| `graph/pipelines/build_graph.py`             | `PIPELINE` importing those registries and composing execution      |
| `graph/pyproject.toml`                       | Graph dependencies, including project reader libraries             |
| `graph/build/<run>/`                         | Derived export files and run evidence                              |

Use `PROJECT_ROOT` from the workspace's `paths` module for existing inputs and managed metadata, and
`GRAPH_ROOT` for graph artifacts. Use package-relative imports;
keep payload access inside loader/pipeline calls. The CLI selects `TOPOLOGY` and
`PIPELINE` from these conventional locations, with `--graph` selecting the folder.

One record set becomes one source package, named by an importable form of its
`@id`, under a folder named for its manifest. Generation is exhaustive over the
manifest, replaces only generated modules, and creates missing authored siblings.
Existing loaders and registrations are not migrated or overwritten. A record set
removed from the manifest leaves an orphaned package, reported and never deleted.
`source generate ... --check` reports each package's freshness without creating
any files.

Generated `RECORDS` holds that package's single record class, excluding nested
field classes; `SourceRow` aliases it for loader annotations. `SOURCE.records`
defaults to `RECORDS`. The manifest's `CONTRACTS` inventory is a contract listing,
not a request to load every record set. Choose participating contracts in
`SOURCES` and concrete input classes in each `Mapping.inputs`. Do not replace
typed inputs with `Any`.

## Source and topology contracts

Import the public contracts from `biotope.graph`:

- `SourceContract(name, metadata, generated, records)` links effective metadata,
  its generated module and participating record classes.
- `Evidence(artifact, version, record_set, location)` identifies a contributor.
  `SourceRecord(value, evidence)` carries a typed value and a tuple of references.
- `Loader[Config, Row]` accepts explicit configuration and yields source records.
  Implement it beside the generated classes using established parsing libraries.
  Biotope and its templates contain no source-format readers.
- `Topology(nodes=(...), edges=(...))` registers dataclasses. Each declares
  `schema_id: ClassVar[str]`. Nodes have distinct `NewType(..., str)` identifiers;
  edges use the corresponding types for `source` and `target`.

Use keyword arguments in graph constructors so property changes fail clearly.
Use optional `display_name: ClassVar[str]` for short, purpose-appropriate diagram
labels. Keep stable `schema_id` identities separate; labels do not change exports
or topology revisions. Python class names provide fallback labels.

Mint namespaced identifiers explicitly; use source-specific namespaces where
cross-source identity is unresolved. Reuse a node type for same-type relation
endpoints rather than inventing a second concept.

Generated fields default to nullable. Curated `biotope:nullable: false` asserts
non-nullability. Known scalars, nested records and repeated fields are supported;
unknown types and `arrayShape` fields use `UnknownValue`. Refine their metadata
before loading non-null values; an unused nullable opaque field can remain `None`.
`Row.__field_refs__` maps attribute names to Croissant field IDs, or a reference
under the record set's own identity when IDs are absent. Extraction rules, descriptions and other metadata stay in
the Croissant file registered by `SOURCE.metadata`; do not copy them into Python.

Graph export supports nullable scalars and string lists without nulls or `|`.
Other property shapes need an explicit project representation.

## Mappings and composition

`Mapping(name, function, inputs, outputs, requirements=(), evidence=())` registers
an annotated function returning an iterable of typed objects. Inputs and outputs
are tuples of classes. Functions may take several inputs and emit several
outputs; keep scientific rationale and evidence near the code.

`Pipeline(name, topology, sources, mappings, run, scope, code_paths, ...)` declares
composition. Optional fields include `settings`, `policies`, `intent`,
`requirements`, `deferrals`, `dependencies` and `variability`. Its `run` receives
a `RunContext`:

- `context.load(contract, loader, config)` invokes a registered loader and checks
  its returned records without coercion.
- `context.map(mapping, *records)` applies a mapping and collects graph objects.
- `context.apply(mapping, *records)` returns evidence-bearing outputs for further
  project processing.
- `context.emit(value, evidence, mapping=<id>)` collects a declared graph output
  with explicitly supplied contributors.
- `context.exclude(policy_key, evidence, count=1)` records exclusions against a
  declared pipeline policy.

Joins, filtering, aggregation and conflict resolution are project Python.
Declare keys, cardinality, unmatched behavior and output grain. Exact duplicates
combine evidence; conflicting values for an ID fail. Edges without an explicit
ID use concept/source/target identity; parallel edges need explicit IDs.
The engine retains graph objects and evidence in memory; project joins may also
retain state. Assess feasibility against the requested execution scope.

Intent is discovered from project metadata or selected with `Pipeline.intent`.
Requirement keys are `entity:<exact intent text>` or `relation:<exact intent text>`;
values are topology concept IDs. Deferrals use the same keys with a reason as
value. Missing bindings or deferrals fail checks. Preserve the requirements;
deferral records a limitation rather than resolving it.
