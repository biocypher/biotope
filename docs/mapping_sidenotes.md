# Typed graph technical notes

These notes expand the [authoring guide](mapping.md). They describe Biotope 0.10's
source generation, typing, reporting and export contracts.

## Source generation

Generation scaffolds record sets, nested `subField` records, repeated values,
and known schema.org/Croissant scalar types. Text, URLs, dates and datetimes are
strings; booleans, integer types and floating-point types become their Python
counterparts. Source precision and extraction details remain in Croissant.
Nullability defaults to `T | None`, with a default of `None` for unloaded fields.
A curated `biotope:nullable: false` asserts a non-null value; loaders must validate
that assertion. Repeated elements are nullable, too.

Unknown types and fields with `arrayShape` become `UnknownValue | None`. Croissant
retains their shape and location; matrix dimensions do not define a row grain.
Refine the contract before loading those values. Supported records can proceed
independently, and unused opaque fields can be `None`. Generation supports this
subset of Croissant; it does not perform general JSON-LD reasoning.

`--out` is the sources package. Each manifest owns one root,
`graph/sources/<manifest>/`, named after the manifest file unless `--package`
overrides it. Its targets are every top-level record set, plus every leaf
`FileObject` or `FileSet` that no record-set field reads; a resource that others are
`containedIn` is packaging, not a target. Each target gets a package holding
`schema.py`, a `SOURCE` registration in `__init__.py` and a placeholder
`loader.py`. The root's generated `__init__.py` collects its packages when
imported, and `graph/sources/inventory.py` collects every root as `INVENTORY`, so
no generated listing can go stale. Helper modules and helper directories without a
`schema.py` are ignored.

A package belongs to the identity its `schema.py` declares — `__record_set__`,
`__file_object__` or `__file_set__` — whatever the directory is called, as long as
the name is a Python identifier. Generation reads that declaration as syntax,
never importing the module. It creates missing files only: a new package is
staged and renamed into place, a package missing its registration or loader is
completed, and an existing schema, registration or loader is never rewritten.

Nothing is written when there is a conflict:

- two packages declare one identity, or a schema declares none or several;
- two entries in the manifest share an `@id`, a file a record set reads included, or a file resource has none;
- a package directory cannot be imported;
- a manifest is already generated into another root, or two manifests would share
  a root name (pass `--package` for the last).

A conflict withholds only the identities it concerns, so `graph check` still
reports every other finding in the root. A source removed from the manifest leaves
an orphaned package; exclude it, then delete its directory. `--check` writes
nothing, and fails when generation would create or change a file or finds a
conflict.

New package names follow record-set `@id`s, falling back to `name` and then a JSON
pointer. Punctuation becomes underscores, keywords and numeric prefixes are
protected, long names are truncated, and a collision among record sets suffixes
every member with a digest of its identity, so reordering a manifest never renames
a package. A file resource is named after its `name`, then its `contentUrl`
basename, then its `@id`, and avoids every name already taken, so it never
displaces a record set. Names therefore depend on the directories that exist when
a package is created.
Generated files keep to 120 columns. A root's `__init__.py` and `inventory.py`
are compared with whitespace normalized, so reformatting them never makes them
stale; the other generated files are yours to format.

A table schema binds each attribute to a Croissant field through `source_field`:
a bare attribute binds the field whose `@id` is `<record set>/<attribute>`,
`source_field("<suffix>")` names another field of the record set, a full `@id`
works where the suffix is empty or itself scoped, and `source_field(None)` declares
a value the source does not supply. New scaffolds require field `@id`s scoped under
their record set; other ids are reported as `source.unscoped_field`. A 0.9 schema's
`__field_refs__` mapping still binds. A document schema declares `__file_object__`
(or `__file_set__`), a `<file @id>/facts` record set and the file's revision; its
fields are the reviewed facts you transcribe. Descriptions, extraction rules,
distributions and extensions stay in the Croissant file registered in
`SOURCE.metadata`.

A record set's revision is a digest of its description and the manifest's
`@context`; a file resource's revision also covers its checksum. Dataset review
notes and other resources do not change it. Generation snapshots every revision it
sees into `.biotope/contracts/<digest>.json`, and `graph check` compares each
schema's `__source_digest__` with the current revision. A difference is
`source.drift`, explained field by field and as a complete JSON-pointer diff
against the recorded revision, including changes to `@context` or to ordering.
Without a recorded revision the drift is still reported, with the current contract.

## Mapping signatures

Parameters must be required and annotated: no `*args`, `**kwargs`, defaults or
missing annotations. Input and output types are concrete dataclasses, or finite
unions of them. Returns are parameterized `Iterable`, `Iterator`, `Generator`,
lists or tuples, including a fixed tuple of different output types.
`Any`, `object`, bare containers and unresolved annotations are rejected at the
mapping boundary, where they would erase the contract.

Values are validated against their declarations as they pass through a mapping or
a loader, without coercion. Fields of source and intermediate records may therefore
be `str`, `int`, `float`, `bool`, `None`, a `NewType`, `list[...]`, `tuple[...]`
(fixed or variadic) or a dataclass. The definition check reports any other field
type, such as `dict` or `set`, as `mapping.contract` or `source.contract` before a
build starts. Graph properties are narrower: nullable scalars and string lists,
as the [typed graph guide](mapping.md) describes.

Registries hold `tuple[MappingEntry, ...]`, a read-only view of mapping identity,
requirements and evidence. Import the concrete `Mapping` object when calling it.

## Definition checks and measurements

Checking discovers source packages statically, imports project declarations,
verifies source contracts, derives topology, checks requirement bindings, and runs
Pyright in strict mode over `Pipeline.code_paths`. Include all sources, loaders,
standardization, alignment, topology, mappings, shared helpers and pipeline
modules. Directory enumeration ignores `.venv`, `venv`,
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

Quality prints its assessment, including failures, and writes no file; it stops
before export. Build records the same assessment in `run.json` and then exports.
Invalid values, conflicts, unresolved endpoints or a selected loader that did not
finish fail the build; `run.json` records failure. Identical nodes/edges combine
evidence. Edges without an explicit ID use a stable hash of concept/source/target,
so parallel edges with different properties need explicit project IDs. A build
replaces its output directory only when it recognizes every file there, and a
failed rebuild keeps the previous build beside `last_failure.json`.

## Metagraph reports

For short diagram labels, add `display_name: ClassVar[str] = "Gene expression"`
beside a concept's `schema_id`. Without it, the viewer uses the Python class name
split into words. Labels are presentation metadata: they do not change IDs,
exported properties or the topology digest. Full IDs remain in the detail panel
and JSON. Relation labels appear on selection/hover; the toolbar can show all.

`graph metagraph` writes a self-contained offline topology viewer to
`<graph>/metagraph.html`, independently of the pipeline. `--out <html>`
changes that location. `--json` emits its description without creating HTML;
it cannot be combined with `--out`. Use `--report <run.json>` to add counts,
property examples, findings and mapping references. The topology
digest must match. The viewer displays the run scope and completion state;
missing measurements stay unmeasured, and loading a report never reruns data.
Only recognized generated reports may be replaced; authored files are preserved.

## Export and provenance

Before a build reads payloads, the writer checks that the installed BioCypher
version is supported. Biotope 0.10 uses BioCypher 0.17.x. The pipeline selects its
export format: `BioCypherWriter("csv")` is the default and
`BioCypherWriter("parquet")` is also supported, the latter needing a Neo4j release
whose import accepts it. After writing, the export directory is checked against
the declared format.

`run.json` (`schema_version` 2) records scope, policies, source metadata and
available versions, code/topology revisions, settings, bindings, dependencies, the
source inventory and exclusions, audits, completion and output locations.
Dependency entries include installed versions and editable/VCS details when
available. Biotope's Python source digest identifies local edits that a package
version cannot. Unspecified variability is reported as unreviewed. `graph_digest`
compares graph content across runs without timestamps or paths. Reproducibility
still depends on the project's external state and code policies.

Every exported node and edge carries `biotope_provenance_id`, a zero-based index
into `provenance.json["records"]`. A record lists the contributing mapping names
and indexes into `evidence`; each evidence entry names a location and a shared
`sources` entry with the artifact, its version and the record set. Identical
provenance is shared, and indexes are local to one build, so distribute
`graph/build/` with the graph. Each output receives the inputs of the mapping call
that produced it, including both sides of a join. This does not mean every input
determined every property: a sample produced by a sample/person mapping also
references the person row. Use smaller mappings where narrower attribution
matters. Aggregates may reference a project-maintained contributor artifact;
Biotope does not infer field-level lineage.

`schema_config.yaml` is derived from Python and carries each concept's
description, its property descriptions and nullability. Export is headless: there
is no synthetic ontology root, and labels use the concept's local name, for
example `example:sample` becomes `Sample`. Concepts sharing a local name are
widened to their full namespaced ID, and a residual collision receives a stable
suffix, so adding a colliding concept can change an existing export label.
BioCypher writes Neo4j import CSVs and a suggested import script under
`biocypher/`. No database is started and no external ontology is downloaded.
Inspect headers, values and provenance before accepting the graph; live database
import and querying are separate work.
