# Typed graph projects

Python defines the target graph and mappings. Croissant describes the sources;
Biotope generates source-record dataclasses, checks definitions, validates
execution, and writes BioCypher files. Concrete loaders and scientific decisions
belong in the graph project. Start with the [working example](tutorial.md).

## Create the workspace

Run `biotope graph scaffold` from the project root when graph authoring is needed.
It creates `graph/` with typed examples, registration modules, pipeline boilerplate,
path constants and graph dependencies. The `_example` files show generated source
records, a loader interface, two nodes, an outgoing relation and a pure mapping.
They describe no project data and stay outside the active registrations. Adapt
them using `graph/README.md`, then remove unused examples. Source generation
remains a separate command over reviewed metadata.

Scaffolding works without initialization or a bake; an existing `graph/` is never
overwritten. No data is scanned or graph executed. Complete the active pipeline's
scope, topology, loaders and mappings before use. The existing `graph build`
command uses Biotope's BioCypher exporter; no project-specific adapter is needed.
The scaffold and working example share one convention: register `SOURCES`,
`TOPOLOGY` and `MAPPINGS` in their folders' `__init__.py` files, then import them
into `pipelines/build_graph.py`.

Keep graph-specific code, metadata corrections, documentation, helper tools and
outputs under `graph/`, adding them only as needed. Raw data, existing purpose and
managed `.biotope/datasets/` stay at the project level. `graph/paths.py` defines
`PROJECT_ROOT` and `GRAPH_ROOT`; use `graph.` or package-relative imports and run
CLI commands from the project root.

## Keep the authorities separate

One record set of one manifest becomes one source package, so adding, removing
or re-encoding an upstream file touches one folder.

| Artifact                                            | Owner and purpose                                           |
| --------------------------------------------------- | ----------------------------------------------------------- |
| `.biotope/datasets/<manifest>.jsonld`               | Effective, curated source descriptions                      |
| `graph/sources/<manifest>/__init__.py`              | Generated `CONTRACTS` inventory of that manifest's packages |
| `graph/sources/<manifest>/<record-set>/schema.py`   | Generated dataclass; regenerate rather than edit            |
| `graph/sources/<manifest>/<record-set>/__init__.py` | Authored `SOURCE` registration; created when absent         |
| `graph/sources/<manifest>/<record-set>/loader.py`   | Authored physical access using established format libraries |
| `graph/sources/__init__.py`                         | Authored `SOURCES` selection                                |
| `graph/topology/<node>/`                            | Authored node and outgoing relation dataclasses             |
| `graph/mappings/`                                   | Pure transformations of typed inputs                        |
| `graph/pipelines/build_graph.py`                    | Source selection, joins, exclusions and execution           |
| `graph/build/<run>/`                                | Derived schema, BioCypher files, provenance and run record  |

Organise mappings by source and group them only where a transformation is
genuinely shared; nothing in the engine depends on their file layout.

Existing YAML mappings and the interactive mapping wizard are retired. There is
no automatic migration. Keep old mappings as reference while authoring Python;
they are no longer executed or checked. `map --purpose` and the existing intent
lists remain research requirements, not an executable graph schema.

## Curate and generate

Review baker's output before generating types. For a correction or an unsupported
input, author a complete Croissant description in a separate file. Describe only
structure established by evidence; include unresolved gaps in the review reason.
Register it as the effective description:

```bash
biotope source register graph/metadata/study.jsonld --name study \
  --reason "Reviewed sheet headers; the image matrix remains opaque" --replace
biotope source generate .biotope/datasets/study.jsonld --out graph/sources
```

Omit `--replace` when adding a new description. Before replacement, the command
reports removed top-level keys, record-set/field IDs and curation notes. It
preserves notes supplied in the replacement and replaces the review reason.
It does not merge descriptions or verify that the reason matches the edit;
reconciling changed values and nested annotations remains the reviewer's job.
Registration protects that
manifest from `add --rebake` and `add --force`. Saved annotations receive the same
protection, including descriptions that a new bake would otherwise discard.
To refresh a curated source:

```bash
biotope add raw/study --bake-to graph/metadata/study-fresh.jsonld
# Reconcile graph/metadata/study-fresh.jsonld with the existing curated description.
biotope source register graph/metadata/study-fresh.jsonld --name raw/study \
  --reason "Reconciled new files with reviewed corrections" --replace
```

`--bake-to` requires one input and a new output file outside that input directory
and `.biotope/datasets`. It writes no tracking changes or annotation scaffold.
Relative source locations still refer to the original data root. Annotation
commands can still edit descriptions and provenance. Generation never changes raw data.

The generator supports record sets, nested `subField` records, repeated values,
and known schema.org/Croissant scalar types. Text, URLs, dates and datetimes are
strings; booleans, integer types and floating-point types become their Python
counterparts. Source precision and extraction details remain in Croissant.
Nullability defaults to `T | None`, with a default of `None` for unloaded fields. A curated `biotope:nullable: false` asserts a
non-null value; loaders must validate that assertion. Repeated elements are
nullable, too.

Unknown types and fields with `arrayShape` become `UnknownValue | None`. Croissant
retains their shape and location; matrix dimensions do not
define a row grain. Refine the contract before loading those values. Supported
records can proceed independently, and unused opaque fields can be `None`.
This is a defined subset of Croissant, not a JSON-LD reasoner or universal matrix
representation.

`--out` is the sources root. Generation is exhaustive: every top-level record
set of the manifest becomes `graph/sources/<manifest>/<record-set>/`, holding one
generated `schema.py` with a single record class, a one-element `RECORDS` tuple
and a `SourceRow` alias for it. `<manifest>` follows the manifest filename unless
`--package` overrides it. Missing sibling `__init__.py` and `loader.py` files are
created and existing authored ones are preserved.

`graph/sources/<manifest>/__init__.py` is generated and exports `CONTRACTS`, every
package's `SOURCE`. Select from it into the authored `SOURCES` registry;
generation does not choose pipeline scope. Because Python imports a parent package
first, importing one package of a manifest imports them all; the modules are
declaration-only, so this reads no payload.

`--check` writes nothing and reports each package as current, missing, stale,
authored, conflict, orphan or renamed. A record set removed from the manifest
leaves an orphaned package: generation reports it and never deletes it, because
its loader is authored work. Removing the package is a project decision;
`graph check` fails only while it remains registered in `SOURCES`.

Package and class names derive from the record set `@id`, falling back to `name`
and then to a JSON pointer. Punctuation becomes underscores, keywords and numeric
prefixes are protected, long names are truncated, and a collision suffixes every
member of the colliding group with a digest of its identity, so reordering a
manifest never renames an unrelated package. `Row.__field_refs__` maps Python
attribute names to original field `@id` values, or a reference under the record
set's own identity when IDs are absent — never a manifest position, so inserting
or removing a record set leaves unrelated packages byte-identical. `Row.__record_set__` identifies the record set in the same way. These are
references to the authoritative Croissant file registered in `SOURCE.metadata`.
Descriptions, extraction rules, distributions and extensions stay there;
generated Python contains no embedded metadata document or metadata-loading code.

Generation is deterministic for the same record-set description, interpretation
context and generator version. Each package carries a freshness digest over its
own record set alone, so editing one record set rewrites one `schema.py`. The generated declarations carry a freshness hash
and import without reading Croissant or source payloads.
Generation writes only the designated module and refuses to overwrite authored Python.
Changes to record-set descriptions, context or generated code fail freshness checks.
Regenerate, review the diff, repair mappings/loaders and restart the checking process.
Dataset review notes, distribution checksums and timestamps do not change the source
contract. The full metadata digest is recorded separately for provenance.

## Define topology and identity

Use dataclasses and a separate `NewType` over `str` for each node identifier.
Relations use those types for `source` and `target`. Put outgoing relation files
beside the source node. Each class has an explicit `schema_id: ClassVar[str]`;
file/class renames do not change this concept ID.

```python
from dataclasses import dataclass
from typing import ClassVar, NewType

PersonId = NewType("PersonId", str)

@dataclass(frozen=True)
class Person:
    schema_id: ClassVar[str] = "study:person"
    id: PersonId
    name: str
```

Mint namespaced identifiers explicitly in project code. Equal local strings from
two studies are not evidence of shared identity. A `NewType` conversion gives
static separation, not uniqueness or biological equivalence. Runtime checks require
`namespace:local-id`, reject conflicting objects with the same ID, and resolve
edge references against the declared endpoint types.

Graph properties support strings, booleans, integers, finite floats, and their
nullable forms. The selected exporter also supports string lists without null
elements or the `|` separator. Other collections, nested graph properties and
unsupported export values fail explicitly; convert them deliberately in mappings.
Source contracts can be richer than exported graph properties.

## Compose loaders and mappings

`Loader[Config, Row]` is a callable returning `Iterable[SourceRecord[Row]]`.
`SourceRecord` pairs a value with `Evidence(artifact, version, record_set, location)`. Use an available checksum, release version or an explicitly labeled
unverified fingerprint; do not claim that a timestamp proves identical data.

Read files only inside explicitly called project loader functions. Decode formats,
missing tokens and categorical representations there. Use established libraries
such as Python's `csv`, PyArrow or h5py; Biotope provides no format readers or
file-dispatch framework. Source-contract validation is strict and performs no
coercion. A loader must report decoding failures with the source location.

Mapping functions accept annotated source or intermediate dataclasses and return
an iterable of typed outputs. They do not open files. They may produce several
nodes/edges, transform properties or mint identifiers. `Mapping` registers a
stable ID, function, input/output types, requirement references and evidence notes.
Keep transforms beside the mapping until reuse warrants a shared module.

`Pipeline` explicitly registers topology, sources, mappings, code paths, its
`run` function, scope, settings, policies and optional intent (otherwise the current project intent is used). Its requirement
bindings use `entity:<exact intent text>` and `relation:<exact intent text>` as
keys and concept IDs as values. Use `deferrals={key: reason}` for agreed gaps.
A required item must have a binding or a stated deferral; checking does not
establish scientific purpose coverage. Rewording a requirement currently requires
updating its binding key. Stable requirement IDs belong to the planned purpose-record work.

In a pipeline, `context.load` validates loaded records; `context.map` calls a
registered mapping and collects graph outputs. `context.apply` returns outputs
with the combined evidence when further preparation is needed. Ordinary Python
owns joins, indexes, aggregation and resource lifetimes. State the inputs, keys,
cardinality, unmatched policy and output grain. Use `context.exclude` to report
an exclusion under a declared policy. The run report aggregates counts per policy
and keeps at most ten evidence references per policy, with an explicit truncation flag.
Keep a project-owned contributor artifact when full exclusion details are needed.
Direct `context.emit` is available for project-authored preparation; supply its
mapping identity and all contributors.

The example holds a people index in memory and streams samples through a
many-to-one join. Biotope retains emitted objects, IDs and contributor references
in memory for conflict/deduplication and endpoint checks. Choose a bounded build;
this iteration has no disk-backed state engine or object-per-pixel requirement.

## Check, execute and inspect

Run from the parent project root with the intended environment activated:

```bash
biotope graph check --json
biotope graph metagraph
# To assess data without export:
biotope graph quality --json
# Or assess and export in one execution:
biotope graph build --out graph/build/review-1
```

All graph commands accept `--graph <folder>`. They use its conventional
`TOPOLOGY` and `PIPELINE` registrations, with relative inputs anchored to the
workspace parent. Prefer package-relative imports so renaming the folder works.

Checking imports project declarations, verifies generated contracts, derives
topology, checks requirement bindings, and runs Pyright in strict mode over
`Pipeline.code_paths`. Include all generated sources, loaders, topology, mappings,
shared helpers and pipeline modules. Directory enumeration ignores `.venv`, `venv`,
`.git` and `__pycache__`; prefer explicit project code directories. Imports must be safe: no source access or
mapping execution at module scope. This boundary is a project contract, not a
sandbox for arbitrary Python. Definition checks work without source payloads.

Quality and build both check definitions, execute the declared pipeline scope
once and assess the final deduplicated graph objects. No automatic sampling,
export-file reading or persisted object cache is involved. Running both commands
executes twice; choose quality when export is unnecessary.

Measurements cover every concept's count; null, whitespace-only and empty-list
properties; isolates and weak components; the three most frequent endpoints per
relation; and actual self-loops. Zero and `False` are usable values. Empty
populations have unmeasured rates. Required empty concepts, wholly missing
properties and self-loops warn without failing the operation; the other rates
are observations. Examples are illustrative: up to three distinct non-null
values in encounter order, strings limited to 160 characters, lists to five
items. Truncation is explicit. Findings retain bounded record and provenance
references. These checks do not establish biological validity.

Quality saves its latest assessment, including failures, to
`<graph>/reports/quality.json`; it stops before export. Build records the same
assessment in its run record and then exports. Invalid values,
conflicts or unresolved endpoints fail the build; `run.json` records failure.
Identical nodes/edges combine evidence. Edges without an explicit ID use a stable
hash of concept/source/target, so parallel edges with different properties need
explicit project IDs. Existing output directories are never overwritten.

For short diagram labels, add `display_name: ClassVar[str] = "Gene expression"`
beside a concept's `schema_id`. Without it, the viewer uses the Python class name
split into words. Labels are presentation metadata: they do not change IDs,
exported properties or the topology digest. Full IDs remain in the detail panel
and JSON. Relation labels appear on selection/hover; the toolbar can show all.

`graph metagraph` writes a self-contained offline topology viewer to
`<graph>/reports/metagraph.html`, independently of the pipeline. `--out <html>`
changes that location. `--json` emits its description without creating HTML;
it cannot be combined with `--out`. Use `--report <quality.json-or-run.json>` to
add counts, property examples, findings and mapping references. The topology
digest must match. The viewer displays the run scope and completion state;
missing measurements stay unmeasured, and loading a report never reruns data.
Only recognized generated reports may be replaced; authored files are preserved.

`run.json` records scope, source metadata and available versions, code/topology
revisions, settings, dependencies, exclusions, completion and output locations.
Dependency entries include installed versions and editable/VCS details when available.
Biotope's Python source digest identifies local edits that a package version cannot.
Unspecified variability is reported as unreviewed.
`graph_digest` compares graph content across runs without timestamps or paths.
Reproducibility still depends on the project's external state and code policies.

`provenance.jsonl` links node/edge IDs to contributing artifacts and row/container
locations. Each output receives the inputs of the mapping call that produced it,
including both sides of a join. This does not mean every input determined every
property: a sample produced by a sample/person mapping also references the person
row. Identical outputs combine these references. Use smaller mappings or explicit
`context.emit` evidence where narrower attribution matters. Aggregates may reference
a project-maintained contributor artifact; Biotope does not infer field-level lineage.

`schema_config.yaml`, `topology.json` and the minimal local ontology are derived
from Python. Readable labels use the full namespaced concept ID, for example
`example:sample` becomes `ExampleSample`. Normalization collisions receive a
stable suffix; adding a colliding concept can therefore change an existing export
label. `topology.json` records the actual exported labels and their semantic IDs.
BioCypher writes Neo4j import CSVs and a suggested import script under `biocypher/`.
No database is started and no external ontology is downloaded. Inspect headers,
values and provenance before accepting the graph; live database import and
querying are separate work.
