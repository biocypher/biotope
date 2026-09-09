# Typed graph definitions and project-owned construction

Status: review fixes, bounded real-data checks and typed scaffold verified; implementation ready for manual acceptance, 9 September 2026. B1–B8 passed; B9 awaits Vlad's Daria/INTRAC scientific review. This is not completed dataset acceptance or release readiness.

This document defines scope, architecture, and acceptance for part 2. [Technical notes](02-typed-graph-engine_sidenotes.md) contain examples and source references. Exact class names, commands, and internal factoring are implementation choices within these boundaries.

## Purpose and outcome

Refactor Biotope's engine so researchers and agents can maintain a graph through typed Python source contracts, topology, and mappings. Given curated Croissant metadata and project-authored loading and transformation code, a project must be able to produce BioCypher files with traceable source evidence.

The workflow is:

1. Bake source metadata and review or complete its descriptions.
1. Generate Python source-record types algorithmically from curated Croissant metadata.
1. Define the target graph in Python.
1. Author typed mappings and source-local loaders inside the graph project.
1. Check definitions without opening source payloads.
1. Explicitly run a project pipeline to load, transform, validate, and export graph data.

Biotope owns contracts, generation, validation, and output integration. Graph projects own concrete loading, scientific transformations, and pipeline composition. Baker describes source formats; project loaders use established format libraries to read values.

## Relationship to other work

Spec 1 on `feat/dataset_harmonization` is the integration base: initial integration `2242c62`, followed by the committed final polish at `2c3676a`. Part 2 started from a clean `2c3676a` working tree. Preserve its metadata, purpose and tracking outcomes while replacing the old mapping engine.

| Spec 1 behavior                                                                                                                                | Part 2 treatment                                                                                                                          |
| ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Baker ingestion and coverage, metadata inspection, purpose capture, annotations, provenance, configuration, status, tracking and Git utilities | Preserve their outcomes; adapt integration points where typed authoring requires it                                                       |
| YAML mappings, wizard/scaffolds and mapping checks                                                                                             | Replace or retire paths tied to the old engine; retain usable purpose capture and metadata inspection, and provide typed authoring/checks |
| Custom readers, source samples in metadata checks, `annotate load`, downloading/discovery and `read`                                           | Keep removed, including reader code in templates                                                                                          |
| Detached graph construction and export                                                                                                         | Implement the selected typed execution path; legacy graph features need no general repair                                                 |

Preservation does not require two mapping engines, a replacement interactive wizard, or CLI/API compatibility. Spec 1 retired automatic alignment suggestions after false equivalence reports; keep that removal. Porting the old executable alignment/merge engine is not required. Reuse working behavior; update affected guidance. Resolve inherited defects only where they still block a required outcome. The spec 1 team's remaining acceptance and published-baker release gate remain theirs; record unresolved dependencies without repeating their audit. Local integration can use the verified local baker until the shared release gate is satisfied.

Richer purpose elicitation and paper experiments remain [part 3](03-purpose-elicitation.pre-spec.md). Retain current purpose information and allow stable references from mappings and topology to research requirements. This spec does not define the future purpose-record schema or its evaluation protocol.

## Responsibility and authority

| Component                | Responsibility                                                                    | Authority and ownership                                                           |
| ------------------------ | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Croissant metadata       | Describe source record sets, fields, identities, locations, and known limitations | Curated project metadata, produced by baker and completed by the agent/researcher |
| Generated source classes | Express source-record shapes and types in Python                                  | Generated from Croissant; never edited manually                                   |
| Source loader            | Read physical data and produce records matching the source contract               | Authored in the graph project, beside its source classes                          |
| Python topology          | Define graph nodes, properties, relations, and endpoint contracts                 | Authored Python is the target graph's only source of truth                        |
| Mapping functions        | Transform typed source records into typed graph objects                           | Authored project Python, organized by source                                      |
| Pipeline                 | Coordinate sources, joins, mappings, policies, validation, and execution          | Explicit project composition using Biotope contracts                              |
| Output adapter           | Translate graph objects and topology into BioCypher files                         | Biotope integration behind a narrow output interface                              |

Create graph boilerplate deterministically with `biotope graph scaffold`, under a dedicated `graph/` folder. Include import-safe registrations, typed topology/source/mapping examples, an unimplemented loader, pipeline wiring, path constants and graph dependencies. Illustrative examples remain unregistered and clearly distinct from project data. The agent adapts them to the purpose and evidence; the active template must not choose scientific concepts or policies, or silently run as a completed pipeline.

Initialization, baking, scaffolding, source generation and execution are independent actions. Generate actual source contracts explicitly with `biotope source generate` from reviewed Croissant; never generate scientific mappings from metadata alone. Use Biotope's existing BioCypher exporter through `graph build`, with outputs under `graph/build/<run>/`. No output-selector framework or duplicate project adapter is needed. Verify template mechanics, generated-contract freshness and static types automatically; research graph acceptance remains manual and in production.

Init must not create graph code or a Python dependency project. Keep graph-specific code, metadata corrections, helper tools, notes and outputs under `graph/`; create optional directories only when needed. Preserve existing raw data, purpose and managed Croissant locations. Refuse existing scaffold destinations rather than overwrite authored work.

Derived YAML, schema diagrams, metagraphs, and output schemas must be generated from topology. They must not become independently editable graph definitions. Source classes remain derived from Croissant. Mappings are authored Python; there must be no second authoritative YAML implementation of the same mapping.

Biotope owns its implementation and release schedule. `kg-build-system` is a design reference, not a required dependency or vendored engine. Credit Paul Ka Po To and the influence of typed authoring, topology organization, and modular construction. Distinguish inspiration from code reuse and preserve applicable notices for reused code. Vlad can invite a bounded contribution after the foundation exists and coordinate the discussed paper participation. Paul's acceptance, schedule and maintenance role do not gate delivery.

## Source descriptions and generated contracts

### Complete and preserve metadata

The agent workflow must account for every selected source artifact. Review baker output, supplement missing information from evidence, and author Croissant descriptions for unsupported inputs where their structure can be established. Keep unresolved fields, opaque files, ambiguities, and partial inspection visible. Do not invent fields, extraction instructions, or completeness claims. Manual description does not add a baker handler or imply that values can be loaded.

Provide a documented route to register authored Croissant and corrections with managed project metadata. Update spec 1's skill restrictions on manual structural descriptions to allow this route. If a selected graph needs information extracted from unstructured evidence, the project may create a derived artifact with its own description and provenance. Completing every opaque input or building an extraction subsystem is not required.

Rebaking must preserve authored corrections or stop with an actionable conflict before replacing them. Use one effective curated Croissant description for generation and record its revision or digest. Reuse annotation support where suitable. A simple preservation/conflict mechanism is sufficient; no general merge editor or metadata versioning service is required.

For explicit `source register --replace`, report removed top-level keys,
record-set/field IDs and curation-note keys before writing. Preserve incoming
review notes; do not silently merge prior values or treat the review reason as
proof of reconciliation.

### Generate declaration-only Python

Generate real, importable Python source files that a standard static checker can inspect. For supported Croissant shapes, map record sets to record classes, fields to attributes, known scalars to Python values, nested records to nested classes, and repeated values to collection types.

Define supported conversions explicitly, starting from the retained baker metadata and selected project needs. Handle invalid Python names, keywords, name collisions, repeated display names, and nested identities deterministically. Preserve references to each attribute's original record-set/field identity; where an ID is absent, retain a documented locator rather than inventing an original ID. Croissant remains authoritative for source locations, extraction rules, descriptions and extensions. Generated Python contains typed declarations, compact source references and freshness information, with no embedded copy of Croissant or metadata-loading machinery. Generation must not flatten the source contract to the inspector's display summary.

Nullability and unknown types require explicit policies. Do not infer non-nullability from incomplete evidence or silently use `Any` to make mappings pass. Unsupported shapes remain identifiable and may block mappings that use them; unrelated supported records can proceed. Preserve meaningful array/shape information; an arbitrary matrix's dimensions do not alone establish its row grain. Universal Croissant code generation is not required.

Generated classes contain declarations only: no file access, loading methods, resource handles, or scientific transformations. Generation works with source payloads absent. For the same generator version and configuration, identical effective metadata produces identical code. Detect stale contracts and require regeneration/review before executing an affected pipeline. Regeneration preserves authored code. Type checking can expose incompatible edits; it cannot identify every semantic effect of a metadata change.

The source-generation CLI creates missing per-source registration and loader
boilerplate. Generated `RECORDS` and `SourceRow` expose the top-level inventory
and its type union. Keep authored siblings on regeneration and global source
selection explicit. Use the scaffold's `SOURCES`, `TOPOLOGY` and `MAPPINGS`
registries consistently in the working example and guidance.

## Python topology

Use ordinary typed Python classes, with standard dataclasses as the baseline. Pydantic is allowed where configuration or runtime validation benefits from it. No custom expression language or relational query compiler is required to obtain static checking.

Define node properties, relation endpoints, and supported value types explicitly. Organize topology by node, with outgoing relations beside that node. Keep graph concept identifiers independent of module paths and class names so moving a file does not silently rename a graph concept. Detect duplicate concept IDs and distinguish semantic changes from code refactoring.

Use semantic identifier types or typed references where they prevent endpoint mix-ups. Converting a raw value into an identifier is an explicit project identity decision; typing does not prove uniqueness, namespace compatibility, or biological equivalence. Equal source-local strings must not silently merge entities across datasets.

Current purpose and required-entity/relation lists remain research requirements or topology references, not another executable schema. Report disagreements and explicit deferrals without silently changing intent. A selected build may omit deferred requirements if its scope and report say so; passing type checks does not establish purpose coverage. Document regeneration and the resulting CLI/API/agent workflow. Automatic migration is not required.

## Loading and transformations

### Source-local loaders

Loaders live beside generated source classes in separate authored files. Each accepts explicit source configuration and produces records, batches, or references satisfying a declared contract. Use established format libraries and available upstream reader APIs; implementation must not depend on a future baker reader API.

Decode source meaning faithfully. Parsing rules may cover compression, sheet/container selection, categorical encodings, and documented missing-value representations. Validate the loaded representation against its contract and report failures with source context. A valid manifest or generated class does not establish that a corresponding value loader exists or works.

Biotope may provide loader interfaces and unimplemented loader templates. It must not introduce a format-dispatch system or source-format readers in its package or templates. Concrete loaders belong to graph projects and use existing parsing libraries. Reusable format-parser improvements belong upstream rather than being duplicated in Biotope.

### Typed mapping functions

Mappings consume typed inputs and produce typed graph objects. They do not perform filesystem access or hidden acquisition. Scientific transformations and identifier policies are explicit Python functions that can be reviewed with small source-record examples.

| Operation                                                    | Location                                          | Reason                                         |
| ------------------------------------------------------------ | ------------------------------------------------- | ---------------------------------------------- |
| Decompress a file or select a sheet                          | Source loader                                     | Physical access                                |
| Decode categorical codes or a documented missing-value token | Source loader                                     | Recover source values                          |
| Harmonize tissue labels into the project's vocabulary        | Mapping                                           | Target meaning                                 |
| Mint canonical graph identifiers                             | Mapping or shared identity policy                 | Graph identity                                 |
| Apply cohort inclusion criteria                              | Mapping/pipeline policy                           | Research purpose                               |
| Join samples to clinical outcomes                            | Explicit preparation step in the mapping pipeline | Combine inputs under declared scientific rules |
| Convert graph objects into BioCypher tuples                  | Output adapter                                    | Output representation                          |

Keep a transformation beside its mapping until actual reuse justifies a shared, clearly named module. Support multiple outputs and explicitly combined inputs; do not assume every mapping is one source row to one node.

Joins and aggregations state their inputs, keys, expected cardinality, unmatched-record treatment, and output grain. Use typed intermediate records where helpful. Loaders must not hide purpose-dependent joins, filtering, or aggregation.

Register participating source contracts, topology, mappings, and pipelines explicitly in Python. Imports, lists or a small registration function are sufficient; no plugin system is required. Keep stable mapping identities, input/output contracts, settings, and evidence references close to their authored code. Mapping-call evidence identifies all inputs of that call on each output; it does not establish per-property dependencies. Do not infer complete field lineage or transformation semantics from arbitrary Python function bodies.

## Execution, validation, and output

Project pipelines explicitly connect loading, preparation, mapping, and writing. They own source selection, resource lifetime, joins, exclusion policies, and duplicate/conflict handling. Biotope provides small reusable interfaces and validation. Introduce interfaces for concrete responsibilities; a checker or writer need not implement a universal compiler/executor module lifecycle.

Keep definition checks separate from execution. Metadata inspection, generation, topology inspection, and static mapping checks must not invoke loaders or mapping functions. Declaration modules must be import-safe, with payload I/O confined to explicitly invoked loader/pipeline functions. Definition checks must work when source payloads are unavailable and must not trigger scans or checksums. This does not change spec 1's explicit baking and file-integrity operations, which read bytes. A sandbox for arbitrary project Python is outside scope.

Warn when intent is absent, purpose or required lists are empty, or registered
concept IDs use the illustrative `example:` namespace. Successful structural
checks must not imply that purpose alignment has been established.

At execution, report value-contract violations, invalid identifiers, unresolved edge references, and conflicts. Intentional exclusions and unmatched inputs follow declared policies and appear in the run report. Do not hide conflicting values through undocumented last-write-wins behavior. Failed or partial execution must not be reported as a complete graph.

Carry source evidence alongside records: source artifact/version, record set, and row/key or container location where available. Graph outputs retain their contributing references, including both sides of a join and contributors to deduplicated entities. Store provenance in properties or a linked sidecar keyed to emitted node/edge identities. Aggregates may use a resolvable reference to a contributor set rather than copying all references onto every output. State limits honestly; a field-level lineage database is not required.

Keep a small run record with metadata/data versions or available fingerprints, topology and mapping revisions, settings, findings, completion state, and output locations. Reuse existing fingerprints with their limitations rather than requiring a new full-data hash pass. Identify external dependencies and intentional variability; arbitrary Python is not automatically reproducible. Repeated runs of the selected deterministic example should agree on graph content, excluding incidental timestamps or output paths.

Provide a BioCypher adapter that derives schema configuration from Python topology and converts typed graph objects to nodes and edges. Preserve identifiers and property types; report unsupported export types rather than silently stringifying values. Use one supported local file-output mode and document its dependency setup. Implicit ontology defaults must not replace the declared topology. Live database import, querying, and additional backend implementations are outside acceptance.

Allow streaming or bounded batches for record-oriented execution, without requiring a Python object per pixel or matrix element. Selected joins, deduplication and reference checks may keep state; document their memory assumptions. Do not build a general disk-backed state engine or optimize every scientific representation in this iteration.

## Scope and implementation latitude

Required: metadata completion/preservation, source-type generation, Python topology and mappings, project loader/pipeline support, definition and runtime validation, explicit provenance, BioCypher file output, and consistent CLI/API/skill guidance.

Excluded: a general expression DSL, query compiler, scheduler, distributed or incremental engine, new reader framework, universal ontology implementation, mandatory full-corpus graph processing, new baker handlers including Zarr, automatic legacy migration, richer interviewing, and paper evaluation infrastructure. Metagraphs and additional schema exports may be derived later; they are not required deliverables here.

Choose interfaces, names, registration mechanics, and use of Pydantic within this contract. Use one standard type checker; Pyright is the default candidate. Check generated contracts, authored topology and mappings with settings that expose the demonstrated errors; do not require a repository-wide typing cleanup. Preserve Biotope's supported Python range where possible and document any necessary change.

Use explicit value-validation and coercion policies. Keep intended decoding visible in loaders, and select validation granularity appropriate to the representation. Expensive per-value model construction for large arrays is not required.

Every change must serve an acceptance criterion or keep a required path working. Start with the smallest usable path; add abstractions only when concrete use requires them. Reorder work, revise technical assumptions, or choose simpler interfaces when evidence warrants it, and record consequential decisions. Do not expand into unrelated repairs, broad dependency/formatting cleanup, performance projects, or features suggested only by legacy code. Remove or detach obsolete engine code where necessary for one clear workflow; a repository-wide cleanup is not a deliverable.

Resolve routine choices autonomously. Ask Vlad only for a missing scientific decision or a change to required scope; continue independent work meanwhile. Record unrelated findings for later work. Do not weaken acceptance or expand the project to work around a blocker.

## Validation and manual acceptance

Manual testing by Vlad is the main acceptance path. Use the [part 2 runbook](02-typed-graph-engine.runbook.md), retaining the Daria/INTRAC local-package setup, full `raw` metadata scope, Daria context workbook, spot checks, and Claude Code workflow. Reuse completed scans unless investigating a defect or changing inputs requires regeneration.

The source scope remains the same; graph execution follows a bounded purpose and selected inputs in each project. Reuse existing purpose decisions and record selected sources, output nodes/relations, identity rules, and expected spot checks before the build. Vlad settles unresolved scientific choices. It need not load every described field, process full matrices, or build complete graphs of both corpora. Manual metadata for an unsupported format is allowed; new Zarr parsing or value loading is not required.

Deliver `02-typed-graph-engine.runbook.md` beside this spec during implementation. It must use actual supported commands and show where artifacts are written. Extend the manual flow to:

1. Review and complete source descriptions, then generate and inspect Python source classes.
1. Define topology and author source-local loaders and typed mappings with the agent.
1. Run the type checker and definition checks. Demonstrate a few useful failures, such as a renamed property or wrong endpoint identifier type, then repair them.
1. Confirm definition checks do not require source payload access; do not move or alter raw data to demonstrate this.
1. Execute a selected pipeline, inspect BioCypher files against the recorded purpose and expected results, and trace a few nodes/edges to source evidence. Review declared exclusions and conflicts. Show a multiple-input preparation step in a selected task or a small authored example; ordinary Python is sufficient.
1. Change a source description or topology property, regenerate/recheck, repair affected mappings, and rerun. Confirm authored code and metadata corrections survive. Repeat a fixed small build and compare graph content.
1. Repeat on the other project and record defects with command, input, expected/observed behavior, and relevant output.

The new agent prompt should continue through project-authored loading and a selected graph build, replacing spec 1's stopping point. The runbook must distinguish metadata-only checks from explicit value access, preserve raw data, and archive outputs without removing curated corrections or authored code. Do not reuse spec 1's cleanup list blindly. Record actual coverage; the existing runbook's full-directory instructions are not evidence that both projects have completed those scans.

Keep automated testing proportionate: a small number of deterministic checks for generator correctness and meaningful regressions, plus the real static checker on authored examples. Add focused tests for defects that warrant regression protection. Manual runs may establish loader, transformation, provenance, and export behavior. No exhaustive type-checker matrix, automated agent harness, duplicated dataset test suite, new testing framework, or repeat of spec 1's complete test audit is required.

Run relevant retained checks at handoff, including collection and CLI startup after import changes. Update tests for intentionally replaced behavior; do not restore obsolete functionality just to satisfy old tests or weaken a valid regression. Static validity, runtime integrity, and scientific usefulness establish different things; report what was verified. No separate automated case is required for each criterion.

### Acceptance criteria

Use `pending`, `in progress`, `passed`, `failed` or `blocked`, with linked evidence. The same run may support several criteria; no separate report per criterion is needed. IDs beginning with B belong to this spec.

| ID  | Status / evidence                                                                                                                   | Required result                                                                                                                                                                                                    |
| --- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| B1  | passed — [source/revision tests](../../tests/graph/test_sources.py), [annotation protection](../../tests/commands/test_annotate.py) | Authored descriptions/corrections can enter managed metadata; selected sources and gaps are accounted for; rebaking preserves edits or stops before overwriting them.                                              |
| B2  | passed — [source tests](../../tests/graph/test_sources.py), [conversion policies](../../docs/mapping.md#curate-and-generate)        | Deterministic generated contracts retain source identities and supported shapes; naming, unknowns, nullability and stale-contract behavior are documented and demonstrated.                                        |
| B3  | passed — [real checker example](../../tests/graph/test_example.py), [semantic topology](../../tests/graph/test_runtime.py)          | Python is the sole topology/mapping authority; file refactoring preserves concept IDs; the real checker detects meaningful property, value-type and endpoint mistakes.                                             |
| B4  | passed — [payload-absent check and project example](../../tests/graph/test_example.py)                                              | Loaders, mappings and pipelines follow the responsibility table; generation and definition checks work without source payload access.                                                                              |
| B5  | passed — [runtime integrity](../../tests/graph/test_runtime.py), [two-source example](../../tests/graph/test_example.py)            | A working pipeline supports typed transformations and multiple inputs, reports invalid values/references and conflicts under declared policies, and carries inspectable provenance.                                |
| B6  | passed — [real export/repeat check](../../tests/graph/test_example.py), [CSV/label regression](../../tests/graph/test_output.py)    | Actual BioCypher node/edge files and derived schema reflect the typed graph; the selected deterministic build repeats with equivalent graph content and an accurate run record.                                    |
| B7  | passed — [metadata/topology repair](../../tests/graph/test_example.py), [curation survival](../../tests/graph/test_sources.py)      | A metadata/topology revision triggers the appropriate regeneration, check or review; affected mappings can be repaired without losing authored files or corrections.                                               |
| B8  | passed — [readiness evidence](#readiness-evidence), [runbook](02-typed-graph-engine.runbook.md)                                     | The spec 1 behaviors identified for preservation remain usable; CLI/API/skill guidance and the part 2 runbook agree with the typed workflow; no custom reader layer or `kg-build-system` dependency is introduced. |
| B9  | pending — Vlad's selected dataset flows and scientific review                                                                       | Vlad completes the selected Daria and INTRAC manual flows, reviews outputs against recorded expectations, and records feedback and actual source coverage; blocking in-scope defects are resolved.                 |

B1–B8 establish implementation readiness using focused checks and a small working example. B9 establishes dataset acceptance. Pending manual feedback or the shared published-baker release gate does not prevent a readiness handoff, but must not be called completed acceptance or release readiness. A defect that prevents a required result blocks its criterion. An unrelated pre-existing failure may be deferred with baseline evidence and a reason. Do not mark the spec complete until every criterion has passed or Vlad has explicitly changed the scope.

## Delivery and progress

Deliver the implementation, minimal project scaffolding/example, updated guidance, and the part 2 runbook. The lead owns integration and this progress record. Preserve unrelated working-tree changes. Check off work only with recorded evidence; the following is a work breakdown, not a fixed sequence.

- [x] Record the actual spec 1 handoff, dependency environment, inherited blockers and first bounded example — B8.
- [x] Connect curated metadata, generated types, topology and static checks — B1–B4.
- [x] Complete a small loader → mapping → BioCypher path, including validation and provenance — B4–B6.
- [x] Exercise revision and multiple-input behavior; finish affected CLI/API/skill guidance and the runbook — B3, B5, B7–B8.
- [x] Record readiness checks and hand off manual commands — B1–B8.
- [x] Double-check real metadata and selected value pipelines on Daria, INTRAC and Open Targets; record results and limitations without changing source projects.
- [x] Strengthen scaffold with inactive typed examples, separate source generation and the existing BioCypher output path; verify template mechanics, leaving research graph validation manual.
- [x] Resolve review 2: source setup, consistent registries, missing-purpose/placeholder diagnostics, replacement-loss reporting and evidence/runbook repairs.
- [ ] Review Vlad's Daria/INTRAC feedback, resolve blocking defects and record acceptance — B9.

Update acceptance, the checkpoint and a short log at meaningful milestones and before interruptions/handoffs. Record consequential decisions with reasons and remaining work, not a transcript. On resumption, verify the workspace against the checkpoint and reuse evidence unless changed code or new failures invalidate it. This spec and its supporting notes are versioned under `.planning/data-harmonization-and-paper/` on `feat/dataset_harmonization`; give delegated agents the relevant revision and any uncommitted updates. Maintain one canonical progress record.

### Resume checkpoint

| Field                     | Current state                                                                                                                                                                                    |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Active work / owner       | Review 2 engineering complete; awaiting Vlad's scientific review                                                                                                                                 |
| Workspace / revisions     | `feat/dataset_harmonization`, base `2c3676a`; implementation is uncommitted. Python 3.12.13, baker 0.3.2 / `3c11839`, BioCypher 0.9.7, Pyright 1.1.411                                           |
| Last verified result      | 175 tests pass; four inherited Baker failures remain. Source setup, preservation, warnings, strict types, 21 wheel assets and all 337 saved Open Targets record sets verified                    |
| Next concrete step        | Regenerate existing source modules (format 3), review source selections and remaining scientific decisions, then record Vlad's B9 feedback                                                       |
| Blockers / external gates | B9 and the published-baker release/CI gate remain pending. The inherited uv source override still expects `../croissant-baker`; local verification does not establish fresh CI/release readiness |
| Delegated work            | None; implementation was serial                                                                                                                                                                  |

### Review follow-up

[Review decisions](02-typed-graph-engine.review-resolution.md) record the disposition
of F1–F15. Source scale/freshness, review rebakes, export labels/escaping, software
identity, file modes and exclusion reporting have focused regressions. The unused
acquisition/decomposition code is retired; manual tracking remains supported.

- [x] Reproduce confirmed defects and fix the affected behavior.
- [x] Reconcile recommendations with preservation, provenance and scope boundaries.
- [x] Update CLI, guide, skills, runbook and part 3 handoff.
- [x] Complete combined tests, internal type checks, documentation and packaging checks.

### Readiness evidence

Current local verification after review 2: **175 passed, four inherited Baker
format failures** (9 September 2026). The failures cover the missing Excel/HDF5
handlers and OME-specific description; they were independently reproduced at
the baseline in [review notes](spec2_review2_sidenotes.md#first-review-fixes-as-reproduced).
Earlier all-green 174-test results belong to the 8 September environment and
remain historical entries in the log. Retained metadata, purpose, annotation,
tracking and Git checks remain. No new full-data scan or repeat of spec 1's
test audit was added.

- [Source checks](../../tests/graph/test_sources.py): curated registration, rebake
  protection, names/collisions, nested identities, singleton locators, unknowns,
  nullability, deterministic output across JSON key order, structural versus bookkeeping
  revisions, review-bake reconciliation and artifact permissions. A 55 × 200-field
  synthetic module passes strict Pyright; using an opaque field as text fails.
  Replacement reports dropped keys and IDs, including nested fields and review notes.
- [Scaffold/source setup](../../tests/graph/test_scaffold.py): import-safe boilerplate,
  metadata-relative registration, current record inventory, preservation of authored
  siblings on regeneration and existing-work/symlink protection. Definition checks
  warn about missing intent, purpose/requirements and registered example concepts.
  The 337-record setup grows to 338 on regeneration, guarding against Pyright's
  parse-depth limit; generated aliases use flat `Union[...]` syntax.
- [Runtime checks](../../tests/graph/test_runtime.py): semantic IDs independent of
  module names, strict values, namespaced IDs, conflicts, endpoint resolution,
  combined evidence and bounded exclusion reporting.
- [CLI/checker/export example](../../tests/graph/test_example.py): checks with raw
  files absent, real property/value/endpoint type errors, two-input transformation,
  source-row failures, actual CSV values and quoted strings, deduplicated provenance,
  repeatable graph digests, stale-source failure and metadata/topology repair.
- [Export regression](../../tests/graph/test_output.py): actual readable labels and
  collision disambiguation; quoted/comma-bearing scalar and string-list values;
  explicit rejection of a literal array separator inside a list item.
- [Retained workflow](../../tests/integration/test_metadata_workflow.py): startup
  without graph execution imports and no-Git metadata/annotation use without staging
  into a parent repository. Annotation corrections now block destructive rebakes too.

At the initial handoff, the [tutorial](../../docs/tutorial.md) was run through nine actual CLI commands
in a scratch project: **3 nodes, 2 edges**, matching repeat digests and unchanged
synthetic payloads. See the local [summary](evidence/typed-engine/manual-summary.json)
and [transcript](evidence/typed-engine/manual-cli.txt). Consulting payloads were not
read or changed; full metadata scope and selected scientific graph acceptance remain B9.

The review pass reran the CLI build/revision scenario with current code. Updated
local results are in [review evidence](evidence/typed-engine/review/).

The historical [real-data check](02-typed-graph-engine.real-data-check.md) covers
all 30 saved Daria manifests, fresh metadata for all 29 INTRAC files and all 1,632
Open Targets Parquet files, plus the authored Open Targets description. Selected
value builds produced 51 nodes/50 edges, 24 nodes/15 edges and 101 nodes/100 edges,
respectively. Values, provenance, repeat digests and checks without payloads passed.
These results predate the current generator and Baker environment. INTRAC's PMID correction was exercised in scratch
metadata; duplicate headers, other metadata limitations and missing Daria workbook
context remain documented. This engineering evidence supports B1–B8 and informs B9;
it does not establish complete scientific graphs or full-corpus value coverage.

Review 2 verification also passed: strict Pyright on the graph package/CLI,
Ruff E/F/I and formatting, pydoclint, the affected skill validator, mdformat,
MkDocs and `git diff --check`. The wheel contains all 21 scaffold assets; its
source-generation command creates import-safe registration/loader files and
passes strict checking without payloads. Historical lock, packaging and CLI
transcripts remain under `evidence/typed-engine/`. These local artifacts are not
installed package files. Runtime checks use Python 3.12; CI retains its
3.10/3.12 matrix and graph extra.

After the generator update, a metadata-only check of the saved Open Targets
description generated all 337 record sets and passed strict Pyright with zero
type errors. Its 442 opaque-field/missing-intent warnings remain visible; this
scratch check did not load payloads, define scientific mappings or build a graph.

### Implementation log

| Date       | Decision / outcome                                                                                                                                                                                                                                                                                     | Evidence / remaining work                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-09-08 | Finalized the spec and integrated the initial `2242c62` handoff.                                                                                                                                                                                                                                       | Historical design notes; implementation later started from clean `2c3676a`.                                                                                                                                                                                                                                                                                                                                                                 |
| 2026-09-08 | Chose a bounded synthetic samples + people join. Added curated registration, source dataclasses and strict topology/runtime contracts.                                                                                                                                                                 | Tests first failed on missing APIs, then passed. No consulting scans or scientific choices required.                                                                                                                                                                                                                                                                                                                                        |
| 2026-09-08 | Replaced YAML authoring, wizard, compiler and generated adapters with ordinary Python. Removed their exclusive tests and unused Jinja dependency.                                                                                                                                                      | One active engine; existing purpose/inspection/tracking outcomes retained.                                                                                                                                                                                                                                                                                                                                                                  |
| 2026-09-08 | Connected Pyright and BioCypher's local Neo4j file writer.                                                                                                                                                                                                                                             | The negative checker test exposed ignored absolute include paths; fixed and guarded against zero/incomplete file analysis. No external ontology defaults.                                                                                                                                                                                                                                                                                   |
| 2026-09-08 | Self-review fixed metadata key-order determinism, singleton locators, safe generated imports, export quoting, source-row errors and annotation preservation.                                                                                                                                           | Focused failing regressions repaired. Annotation staging also now uses the existing project-Git guard.                                                                                                                                                                                                                                                                                                                                      |
| 2026-09-08 | Completed example, CLI/API/skill guidance, runbook, packaging and readiness checks.                                                                                                                                                                                                                    | B1–B8 passed. Graph objects/evidence remain in memory; unsupported source shapes and export values fail explicitly. B9/release gates remain pending.                                                                                                                                                                                                                                                                                        |
| 2026-09-08 | Resolved the independent review: bounded checker complexity, review-bake route, structural freshness, readable labels, bounded exclusions and software/file-mode integrity. Retained annotation protection and mapping-call evidence; requirement IDs remain part 3.                                   | [Disposition of F1–F15](02-typed-graph-engine.review-resolution.md). 174 tests and strict engine checks pass. B1–B8 verified; B9 and release gate pending.                                                                                                                                                                                                                                                                                  |
| 2026-09-08 | Verified real Daria, INTRAC and Open Targets metadata and bounded typed pipelines in disposable projects. Preserved source projects; added no production readers or permanent test suite.                                                                                                              | [Coverage, findings and rerun instructions](02-typed-graph-engine.real-data-check.md). Output values/provenance and repeat digests pass. No new implementation defect; B9 scientific acceptance remains pending.                                                                                                                                                                                                                            |
| 2026-09-09 | Made init create only required project files and the configuration directory. Existing add/register writers create metadata directories on demand. Updated two existing tests before implementation; no new test cases.                                                                                | Init, empty-project inspection, first add and source checks pass (15 selected checks). Four Baker format checks fail identically with the original HEAD init loaded: Excel/HDF5 handlers unavailable and OME described as a generic image. These are independent of the init change; no upstream code was changed. Ruff, formatting and diff checks pass.                                                                                   |
| 2026-09-09 | Reworked add output around fixed status/path columns, source-relative wrapping, live warnings/extraction failures, confirmed description rows and concise artifact summaries. Added add --json using the same full scan evidence; removed the abandoned verbose-only approach.                         | Two focused output scenarios added after failing first. 27 add/workflow checks pass; full suite: 172 passed, four unchanged Baker format failures recorded above. Checked actual 80-column terminal output, 64-column wrapping, grouped Parquet files, JSON noise isolation, review bakes, multiple single-file inputs and rejected curated rebakes. See the command guide for the JSON contract.                                           |
| 2026-09-09 | Reworked map inspect into wrapping source blocks, declared type/field columns and nested field trees. Removed retired selector tutorials and identifier guesses. JSON v2 retains exact IDs, nested fields, source descriptors, distribution references and extension metadata; load errors use stderr. | Replaced three inspector tests with two broader scenarios, failing first; extended an existing error test. 26 focused checks pass; full suite: 171 passed, the same four Baker handler failures above. Verified all 307 INTRAC and 4,003 Open Targets fields against saved metadata and rendered both at 64/80 columns; checked INTRAC through the CLI in a terminal. No source payloads read.                                              |
| 2026-09-09 | Graph workspace follow-up: added deterministic graph scaffold, moved graph dependency setup out of init, and moved the working example under graph/. Updated skill and runbook to separate mechanical setup from scientific authoring.                                                                 | Passed: standalone scaffold and strict template checks; existing-file/symlink protection; real checker, build and revision tests with a clean project root. Packaged wheel creates all ten template files. Full suite: 172 passed, the same four Baker handler failures above. Pyright, Ruff and skill validation pass. Tests failed first. BioCypher import-time disk logging is replaced by stderr logging when no handler is configured. |

| 2026-09-09 | Strengthened the scaffold with inactive typed source, topology, relation, mapping and pipeline examples. The example contract is generated from illustrative Croissant; its loader is unimplemented. Kept actual source generation separate and documented the existing BioCypher exporter. Updated README, skill and runbook. | Extended the existing scaffold test before implementation; no added test cases or research-graph harness. Definition/freshness checks, strict Pyright, Ruff, pydoclint, skill validation and wheel smoke check pass (all 19 assets preserved). Full suite: 172 passed, the same four inherited Baker handler failures. Generated code is excluded from formatting and verified against metadata. Research graph acceptance remains manual. |

| 2026-09-09 | Resolved review 2: completed per-source setup, unified the example/scaffold registries, added purpose/placeholder warnings and metadata-removal reporting, restored evidence summaries and repaired runbook links. Kept explicit replacement and source selection; deferred unrelated performance work. | Regressions failed first. Current full suite: 175 passed, four inherited Baker failures. Strict types, lint/format, docstrings, skill, documentation and 21 packaged assets verified. A metadata-only Open Targets check exposed and verified the flat-union fix across 337 record sets; the preservation regression covers growth to 338. No research graph was built. [Disposition](02-typed-graph-engine.review-resolution.md#second-review). |

| 2026-09-09 | Finalized the skill and its two references around independent CLI steps, graph/ ownership, generated source packages, authored registries and manual scientific acceptance. Removed duplicated workflow commands and unconditional local installation. | Checked guidance against scaffold, public contracts and CLI help. Skill/frontmatter, Markdown and local links verified; no dataset execution or new test harness. |

| 2026-09-09 | Removed embedded Croissant descriptors and the dataclass-mutating decorator. Generated source modules now contain typed declarations, compact field references and freshness hashes; Croissant remains authoritative. Regenerated the scaffold example and aligned the guide and skill. | Updated existing regressions before implementation. All 13 graph tests pass, including 11,000 fields and source-package regeneration. Saved Open Targets metadata generates 337 record sets / 4,003 fields and passes strict Pyright without payload reads. Engine types, lint, formatting, docstrings and skill validation pass. Existing projects must regenerate source modules; authored loaders and registrations remain preserved. |

## Delegation

When delegation is authorized by the session, use it only for a bounded task that can run independently while the lead does useful work. Settle shared contracts before parallel edits; avoid duplicate exploration and dependent tasks assigned too early. Serial work is appropriate when coordination would cost more than it saves.

Give each assignment its outcome, acceptance IDs, relevant context/paths, exclusions, dependencies, owned files or read-only boundary, and expected evidence. One agent edits each shared file at a time; coordinate explicit handoffs. Pass this spec and only the context needed for the slice. Reuse an existing agent for follow-ups where practical. Delegates follow the same limited testing scope; no independent full-data scans or broader audits.

The lead reviews returned changes/findings, exact checks/results and remaining risks, integrates them, and performs proportionate combined checks before updating acceptance. Keep one progress record. Wait for required results using notifications or bounded waits, and stop delegating once the required work is complete.
