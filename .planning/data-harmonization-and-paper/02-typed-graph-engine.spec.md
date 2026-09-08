# Typed graph definitions and project-owned construction

Status: specification reviewed and finalized, 8 September 2026. Implementation and acceptance have not started. Build on spec 1's implementation handoff, including its working changes.

This document defines scope, architecture, and acceptance for part 2. [Technical notes](02-typed-graph-engine_sidenotes.md) contain examples and source references. Exact class names, commands, and internal factoring are implementation choices within these boundaries.

## Purpose and outcome

Refactor Biotope's engine so researchers and agents can maintain a graph through typed Python source contracts, topology, and mappings. Given curated Croissant metadata and project-authored loading and transformation code, a project must be able to produce BioCypher files with traceable source evidence.

The workflow is:

1. Bake source metadata and review or complete its descriptions.
2. Generate Python source-record types algorithmically from curated Croissant metadata.
3. Define the target graph in Python.
4. Author typed mappings and source-local loaders inside the graph project.
5. Check definitions without opening source payloads.
6. Explicitly run a project pipeline to load, transform, validate, and export graph data.

Biotope owns contracts, generation, validation, and output integration. Graph projects own concrete loading, scientific transformations, and pipeline composition. Baker describes source formats; project loaders use established format libraries to read values.

## Relationship to other work

[Spec 1](01-croissant-baker-update.spec.md) on `feat/dataset_harmonization` is the integration base. Its implementation, including Daria's mapping feedback fixes, is committed at `2242c62`. Verify the current branch, working changes and dependency environment before editing shared modules. Coordinate with its owner; do not overwrite or independently recreate their work.

| Spec 1 behavior | Part 2 treatment |
| --- | --- |
| Baker ingestion and coverage, metadata inspection, purpose capture, metadata-based alignment suggestions, annotations, provenance, configuration, status, tracking and Git utilities | Preserve their outcomes; adapt integration points where typed authoring requires it |
| YAML mappings, wizard/scaffolds and mapping checks | Replace or retire paths tied to the old engine; retain usable purpose capture and metadata inspection, and provide typed authoring/checks |
| Custom readers, source samples in metadata checks, `annotate load`, downloading/discovery and `read` | Keep removed, including reader code in templates |
| Detached graph construction and export | Implement the selected typed execution path; legacy graph features need no general repair |

Preservation does not require two mapping engines, a replacement interactive wizard, or CLI/API compatibility. Alignment suggestions remain advisory; porting the old executable alignment/merge engine is not required. Reuse working behavior; update affected guidance. Resolve inherited defects only where they still block a required outcome. The spec 1 team's remaining acceptance and published-baker release gate remain theirs; record unresolved dependencies without repeating their audit. Local integration can use the verified local baker until the shared release gate is satisfied.

Richer purpose elicitation and paper experiments remain [part 3](03-purpose-elicitation.pre-spec.md). Retain current purpose information and allow stable references from mappings and topology to research requirements. This spec does not define the future purpose-record schema or its evaluation protocol.

## Responsibility and authority

| Component | Responsibility | Authority and ownership |
| --- | --- | --- |
| Croissant metadata | Describe source record sets, fields, identities, locations, and known limitations | Curated project metadata, produced by baker and completed by the agent/researcher |
| Generated source classes | Express source-record shapes and types in Python | Generated from Croissant; never edited manually |
| Source loader | Read physical data and produce records matching the source contract | Authored in the graph project, beside its source classes |
| Python topology | Define graph nodes, properties, relations, and endpoint contracts | Authored Python is the target graph's only source of truth |
| Mapping functions | Transform typed source records into typed graph objects | Authored project Python, organized by source |
| Pipeline | Coordinate sources, joins, mappings, policies, validation, and execution | Explicit project composition using Biotope contracts |
| Output adapter | Translate graph objects and topology into BioCypher files | Biotope integration behind a narrow output interface |

Derived YAML, schema diagrams, metagraphs, and output schemas must be generated from topology. They must not become independently editable graph definitions. Source classes remain derived from Croissant. Mappings are authored Python; there must be no second authoritative YAML implementation of the same mapping.

Biotope owns its implementation and release schedule. `kg-build-system` is a design reference, not a required dependency or vendored engine. Credit Paul Ka Po To and the influence of typed authoring, topology organization, and modular construction. Distinguish inspiration from code reuse and preserve applicable notices for reused code. Vlad can invite a bounded contribution after the foundation exists and coordinate the discussed paper participation. Paul's acceptance, schedule and maintenance role do not gate delivery.

## Source descriptions and generated contracts

### Complete and preserve metadata

The agent workflow must account for every selected source artifact. Review baker output, supplement missing information from evidence, and author Croissant descriptions for unsupported inputs where their structure can be established. Keep unresolved fields, opaque files, ambiguities, and partial inspection visible. Do not invent fields, extraction instructions, or completeness claims. Manual description does not add a baker handler or imply that values can be loaded.

Provide a documented route to register authored Croissant and corrections with managed project metadata. Update spec 1's skill restrictions on manual structural descriptions to allow this route. If a selected graph needs information extracted from unstructured evidence, the project may create a derived artifact with its own description and provenance. Completing every opaque input or building an extraction subsystem is not required.

Rebaking must preserve authored corrections or stop with an actionable conflict before replacing them. Use one effective curated Croissant description for generation and record its revision or digest. Reuse annotation support where suitable. A simple preservation/conflict mechanism is sufficient; no general merge editor or metadata versioning service is required.

### Generate declaration-only Python

Generate real, importable Python source files that a standard static checker can inspect. For supported Croissant shapes, map record sets to record classes, fields to attributes, known scalars to Python values, nested records to nested classes, and repeated values to collection types.

Define supported conversions explicitly, starting from the retained baker metadata and selected project needs. Handle invalid Python names, keywords, name collisions, repeated display names, and nested identities deterministically. Preserve each attribute's original record-set/field identity; where an ID is absent, retain a documented locator rather than inventing an original ID. Source locations, extraction information, descriptions, and references remain available through metadata or descriptors. Generation must not flatten the source contract to the inspector's display summary.

Nullability and unknown types require explicit policies. Do not infer non-nullability from incomplete evidence or silently use `Any` to make mappings pass. Unsupported shapes remain identifiable and may block mappings that use them; unrelated supported records can proceed. Preserve meaningful array/shape information; an arbitrary matrix's dimensions do not alone establish its row grain. Universal Croissant code generation is not required.

Generated classes contain declarations only: no file access, loading methods, resource handles, or scientific transformations. Generation works with source payloads absent. For the same generator version and configuration, identical effective metadata produces identical code. Detect stale contracts and require regeneration/review before executing an affected pipeline. Regeneration preserves authored code. Type checking can expose incompatible edits; it cannot identify every semantic effect of a metadata change.

## Python topology

Use ordinary typed Python classes, with standard dataclasses as the baseline. Pydantic is allowed where configuration or runtime validation benefits from it. No custom expression language or relational query compiler is required to obtain static checking.

Define node properties, relation endpoints, and supported value types explicitly. Organize topology by node, with outgoing relations beside that node. Keep graph concept identifiers independent of module paths and class names so moving a file does not silently rename a graph concept. Detect duplicate concept IDs and distinguish semantic changes from code refactoring.

Use semantic identifier types or typed references where they prevent endpoint mix-ups. Converting a raw value into an identifier is an explicit project identity decision; typing does not prove uniqueness, namespace compatibility, or biological equivalence. Equal source-local strings must not silently merge entities across datasets.

Current purpose and required-entity/relation lists remain research requirements or topology references, not another executable schema. Report disagreements and explicit deferrals without silently changing intent. A selected build may omit deferred requirements if its scope and report say so; passing type checks does not establish purpose coverage. Document regeneration and the resulting CLI/API/agent workflow. Automatic migration is not required.

## Loading and transformations

### Source-local loaders

Loaders live beside generated source classes in separate authored files. Each accepts explicit source configuration and produces records, batches, or references satisfying a declared contract. Use established format libraries and available upstream reader APIs; implementation must not depend on a future baker reader API.

Decode source meaning faithfully. Parsing rules may cover compression, sheet/container selection, categorical encodings, and documented missing-value representations. Validate the loaded representation against its contract and report failures with source context. A valid manifest or generated class does not establish that a corresponding value loader exists or works.

Biotope may provide loader interfaces and empty project scaffolds. It must not introduce a format-dispatch system or source-format readers in its package or templates. Concrete loaders belong to graph projects and use existing parsing libraries. Reusable format-parser improvements belong upstream rather than being duplicated in Biotope.

### Typed mapping functions

Mappings consume typed inputs and produce typed graph objects. They do not perform filesystem access or hidden acquisition. Scientific transformations and identifier policies are explicit Python functions that can be reviewed with small source-record examples.

| Operation | Location | Reason |
| --- | --- | --- |
| Decompress a file or select a sheet | Source loader | Physical access |
| Decode categorical codes or a documented missing-value token | Source loader | Recover source values |
| Harmonize tissue labels into the project's vocabulary | Mapping | Target meaning |
| Mint canonical graph identifiers | Mapping or shared identity policy | Graph identity |
| Apply cohort inclusion criteria | Mapping/pipeline policy | Research purpose |
| Join samples to clinical outcomes | Explicit preparation step in the mapping pipeline | Combine inputs under declared scientific rules |
| Convert graph objects into BioCypher tuples | Output adapter | Output representation |

Keep a transformation beside its mapping until actual reuse justifies a shared, clearly named module. Support multiple outputs and explicitly combined inputs; do not assume every mapping is one source row to one node.

Joins and aggregations state their inputs, keys, expected cardinality, unmatched-record treatment, and output grain. Use typed intermediate records where helpful. Loaders must not hide purpose-dependent joins, filtering, or aggregation.

Register participating source contracts, topology, mappings, and pipelines explicitly in Python. Imports, lists or a small registration function are sufficient; no plugin system is required. Keep stable mapping identities, input/output contracts, settings, and evidence references close to their authored code. Do not infer complete field lineage or transformation semantics from arbitrary Python function bodies.

## Execution, validation, and output

Project pipelines explicitly connect loading, preparation, mapping, and writing. They own source selection, resource lifetime, joins, exclusion policies, and duplicate/conflict handling. Biotope provides small reusable interfaces and validation. Introduce interfaces for concrete responsibilities; a checker or writer need not implement a universal compiler/executor module lifecycle.

Keep definition checks separate from execution. Metadata inspection, generation, topology inspection, and static mapping checks must not invoke loaders or mapping functions. Declaration modules must be import-safe, with payload I/O confined to explicitly invoked loader/pipeline functions. Definition checks must work when source payloads are unavailable and must not trigger scans or checksums. This does not change spec 1's explicit baking and file-integrity operations, which read bytes. A sandbox for arbitrary project Python is outside scope.

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

Manual testing by Vlad is the main acceptance path. Extend the existing [Daria and INTRAC runbook](01-croissant-baker-update.runbook.md), using the same project directories, local-package setup, full `raw` metadata scope, Daria context workbook, spot checks, and Claude Code workflow. Reuse completed scans unless investigating a defect or changing inputs requires regeneration.

The source scope remains the same; graph execution follows a bounded purpose and selected inputs in each project. Reuse existing purpose decisions and record selected sources, output nodes/relations, identity rules, and expected spot checks before the build. Vlad settles unresolved scientific choices. It need not load every described field, process full matrices, or build complete graphs of both corpora. Manual metadata for an unsupported format is allowed; new Zarr parsing or value loading is not required.

Deliver `02-typed-graph-engine.runbook.md` beside this spec during implementation. It must use actual supported commands and show where artifacts are written. Extend the manual flow to:

1. Review and complete source descriptions, then generate and inspect Python source classes.
2. Define topology and author source-local loaders and typed mappings with the agent.
3. Run the type checker and definition checks. Demonstrate a few useful failures, such as a renamed property or wrong endpoint identifier type, then repair them.
4. Confirm definition checks do not require source payload access; do not move or alter raw data to demonstrate this.
5. Execute a selected pipeline, inspect BioCypher files against the recorded purpose and expected results, and trace a few nodes/edges to source evidence. Review declared exclusions and conflicts. Show a multiple-input preparation step in a selected task or a small authored example; ordinary Python is sufficient.
6. Change a source description or topology property, regenerate/recheck, repair affected mappings, and rerun. Confirm authored code and metadata corrections survive. Repeat a fixed small build and compare graph content.
7. Repeat on the other project and record defects with command, input, expected/observed behavior, and relevant output.

The new agent prompt should continue through project-authored loading and a selected graph build, replacing spec 1's stopping point. The runbook must distinguish metadata-only checks from explicit value access, preserve raw data, and archive outputs without removing curated corrections or authored code. Do not reuse spec 1's cleanup list blindly. Record actual coverage; the existing runbook's full-directory instructions are not evidence that both projects have completed those scans.

Keep automated testing proportionate: a small number of deterministic checks for generator correctness and meaningful regressions, plus the real static checker on authored examples. Add focused tests for defects that warrant regression protection. Manual runs may establish loader, transformation, provenance, and export behavior. No exhaustive type-checker matrix, automated agent harness, duplicated dataset test suite, new testing framework, or repeat of spec 1's complete test audit is required.

Run relevant retained checks at handoff, including collection and CLI startup after import changes. Update tests for intentionally replaced behavior; do not restore obsolete functionality just to satisfy old tests or weaken a valid regression. Static validity, runtime integrity, and scientific usefulness establish different things; report what was verified. No separate automated case is required for each criterion.

### Acceptance criteria

Use `pending`, `in progress`, `passed`, `failed` or `blocked`, with linked evidence. The same run may support several criteria; no separate report per criterion is needed. IDs beginning with B belong to this spec.

| ID | Status / evidence | Required result |
| --- | --- | --- |
| B1 | pending | Authored descriptions/corrections can enter managed metadata; selected sources and gaps are accounted for; rebaking preserves edits or stops before overwriting them. |
| B2 | pending | Deterministic generated contracts retain source identities and supported shapes; naming, unknowns, nullability and stale-contract behavior are documented and demonstrated. |
| B3 | pending | Python is the sole topology/mapping authority; file refactoring preserves concept IDs; the real checker detects meaningful property, value-type and endpoint mistakes. |
| B4 | pending | Loaders, mappings and pipelines follow the responsibility table; generation and definition checks work without source payload access. |
| B5 | pending | A working pipeline supports typed transformations and multiple inputs, reports invalid values/references and conflicts under declared policies, and carries inspectable provenance. |
| B6 | pending | Actual BioCypher node/edge files and derived schema reflect the typed graph; the selected deterministic build repeats with equivalent graph content and an accurate run record. |
| B7 | pending | A metadata/topology revision triggers the appropriate regeneration, check or review; affected mappings can be repaired without losing authored files or corrections. |
| B8 | pending | The spec 1 behaviors identified for preservation remain usable; CLI/API/skill guidance and the part 2 runbook agree with the typed workflow; no custom reader layer or `kg-build-system` dependency is introduced. |
| B9 | pending | Vlad completes the selected Daria and INTRAC manual flows, reviews outputs against recorded expectations, and records feedback and actual source coverage; blocking in-scope defects are resolved. |

B1–B8 establish implementation readiness using focused checks and a small working example. B9 establishes dataset acceptance. Pending manual feedback or the shared published-baker release gate does not prevent a readiness handoff, but must not be called completed acceptance or release readiness. A defect that prevents a required result blocks its criterion. An unrelated pre-existing failure may be deferred with baseline evidence and a reason. Do not mark the spec complete until every criterion has passed or Vlad has explicitly changed the scope.

## Delivery and progress

Deliver the implementation, minimal project scaffolding/example, updated guidance, and the part 2 runbook. The lead owns integration and this progress record. Preserve unrelated working-tree changes. Check off work only with recorded evidence; the following is a work breakdown, not a fixed sequence.

- [ ] Record the actual spec 1 handoff, dependency environment, inherited blockers and first bounded example — B8.
- [ ] Connect curated metadata, generated types, topology and static checks — B1–B4.
- [ ] Complete a small loader → mapping → BioCypher path, including validation and provenance — B4–B6.
- [ ] Exercise revision and multiple-input behavior; finish affected CLI/API/skill guidance and the runbook — B3, B5, B7–B8.
- [ ] Record readiness checks and hand off manual commands — B1–B8.
- [ ] Review Vlad's Daria/INTRAC feedback, resolve blocking defects and record acceptance — B9.

Update acceptance, the checkpoint and a short log at meaningful milestones and before interruptions/handoffs. Record consequential decisions with reasons and remaining work, not a transcript. On resumption, verify the workspace against the checkpoint and reuse evidence unless changed code or new failures invalidate it. This spec and its supporting notes are versioned under `.planning/data-harmonization-and-paper/` on `feat/dataset_harmonization`; give delegated agents the relevant revision and any uncommitted updates. Maintain one canonical progress record.

### Resume checkpoint

| Field | Current state |
| --- | --- |
| Active work / owner | Specification review complete; no implementation owner active |
| Workspace / revisions | Canonical spec: `.planning/data-harmonization-and-paper/02-typed-graph-engine.spec.md` on `feat/dataset_harmonization`; spec 1 implementation base: `2242c62` |
| Last verified result | Spec 1 commit and updated handoff inspected; its record reports Daria mapping fixes verified. No new code, source scans or graph runs for this handoff |
| Next concrete step | Verify the integration environment and any changes after `2242c62`, record the baker revision, then build one bounded path |
| Blockers / external gates | Spec 1 full-directory/INTRAC review, B9 manual acceptance and the published-baker release gate remain pending |
| Delegated work | None; record owners, file boundaries and pending results if used |

### Implementation log

| Date | Change / decision | Evidence and next step |
| --- | --- | --- |
| 2026-09-08 | Final review clarified integration, metadata authoring, bounded scope, completion rules and delegation; retired the pre-spec. | [Review notes](02-typed-graph-engine_sidenotes.md#final-review-and-spec-1-handoff). Implementation and B1–B9 remain pending. |
| 2026-09-08 | Integrated the finalized documents into `feat/dataset_harmonization` after spec 1 commit `2242c62`; made repository links portable and updated the handoff record. | Documentation checks only. Part 2 implementation and acceptance remain pending. |

## Delegation

When delegation is authorized by the session, use it only for a bounded task that can run independently while the lead does useful work. Settle shared contracts before parallel edits; avoid duplicate exploration and dependent tasks assigned too early. Serial work is appropriate when coordination would cost more than it saves.

Give each assignment its outcome, acceptance IDs, relevant context/paths, exclusions, dependencies, owned files or read-only boundary, and expected evidence. One agent edits each shared file at a time; coordinate explicit handoffs. Pass this spec and only the context needed for the slice. Reuse an existing agent for follow-ups where practical. Delegates follow the same limited testing scope; no independent full-data scans or broader audits.

The lead reviews returned changes/findings, exact checks/results and remaining risks, integrates them, and performs proportionate combined checks before updating acceptance. Keep one progress record. Wait for required results using notifications or bounded waits, and stop delegating once the required work is complete.
