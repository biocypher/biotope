# Typed graph technical notes

These notes expand the [authoring guide](mapping.md). They describe Biotope 0.9's
source generation, typing, reporting and export contracts.

## Source generation

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
Generation supports this subset of Croissant; it does not perform general JSON-LD reasoning.

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
set's own identity when field IDs are absent. Stable record-set IDs keep these references unchanged when other record sets are inserted or removed. `Row.__record_set__` identifies the record set in the same way. These are
references to the authoritative Croissant file registered in `SOURCE.metadata`.
Descriptions, extraction rules, distributions and extensions stay there;
generated Python contains no embedded metadata document or metadata-loading code.

Generation is deterministic for the same record-set description, interpretation
context and generator version. A digest covers each record set and its context;
editing one record set updates its schema without rewriting unrelated schemas.
Generation also updates the manifest inventory and preserves authored siblings.
Changes to record-set descriptions, context or generated code fail freshness checks.
Regenerate, review the diff, repair mappings/loaders and restart the checking process.
Dataset review notes, distribution checksums and timestamps do not change the source
contract. The full metadata digest is recorded separately for provenance.

## Mapping signatures

Parameters must be required and annotated: no `*args`, `**kwargs`, defaults or
missing annotations. Input and output types are concrete dataclasses, or finite
unions of them. Returns are parameterized `Iterable`, `Iterator`, `Generator`,
lists or tuples, including a fixed tuple of different output types.
`Any`, `object`, bare containers and unresolved annotations are rejected at the
mapping boundary, where they would erase the contract.

Registries hold `tuple[MappingEntry, ...]`, a read-only view of mapping identity,
requirements and evidence. Import the concrete `Mapping` object when calling it.

## Definition checks and measurements

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

## Metagraph reports

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

## Export and provenance

Before a build reads payloads, the writer checks that the installed BioCypher
version is supported. Biotope 0.9 uses BioCypher 0.17.x. The pipeline selects its export format: `BioCypherWriter("csv")` is the default and `BioCypherWriter("parquet")`
is also supported, the latter needing a Neo4j release whose import accepts it.
After writing, the export directory is checked against the declared format.

`run.json` records scope, source metadata and available versions, code/topology
revisions, settings, dependencies, exclusions, audits, validation results,
the generated query context, completion and output locations.
Dependency entries include installed versions and editable/VCS details when available.
Biotope's Python source digest identifies local edits that a package version cannot.
Unspecified variability is reported as unreviewed.
`graph_digest` compares graph content across runs without timestamps or paths.
Reproducibility still depends on the project's external state and code policies.

`provenance.jsonl` links node/edge IDs to contributing artifacts and row/container
locations. Each output receives the inputs of the mapping call that produced it,
including both sides of a join. This does not mean every input determined every
property: a sample produced by a sample/person mapping also references the person
row. Identical outputs combine these references. Use smaller mappings where
narrower attribution matters. Aggregates may reference
a project-maintained contributor artifact; Biotope does not infer field-level lineage.

`query_context.json` is generated from the same declarations plus the run's own
evidence: concept and property descriptions with their export labels, the
interpretation rules, capabilities and their validation states, the selection
policies, exclusion counts and stage audits, settings, stated variability and
source versions. Its essential content is also exported as rows under the
reserved `BiotopeQueryContext` label, so a consumer with only a database session
can read the same rules with `MATCH (c:BiotopeQueryContext) RETURN c`. Those rows
carry system metadata and stay out of the project's own population counts.

`schema_config.yaml`, `topology.json` and the minimal local ontology are derived
from Python. Readable labels use the full namespaced concept ID, for example
`example:sample` becomes `ExampleSample`. Normalization collisions receive a
stable suffix; adding a colliding concept can therefore change an existing export
label. `topology.json` records the actual exported labels and their semantic IDs.
BioCypher writes Neo4j import CSVs and a suggested import script under `biocypher/`.
No database is started and no external ontology is downloaded. Inspect headers,
values and provenance before accepting the graph; live database import and
querying are separate work.
