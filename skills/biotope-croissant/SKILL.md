---
name: biotope-croissant
description: Describe and curate local data with Croissant, capture research purpose, and author typed graph projects with Biotope. Use for Biotope ingestion, generated source contracts, Python topology and mappings, project-owned loaders, and BioCypher file builds. Database import and querying are separate workflows.
---

# Biotope graph projects

Use Biotope commands for scanning, scaffolding, source generation, checks and
export. The agent owns purpose alignment, metadata curation and project-specific
Python: identity choices, decoding, transformations, joins and graph composition.

Initialization, baking, scaffolding, source generation, checking and building are
independent steps. Perform the steps needed for the user's request; a metadata or
mapping task does not imply graph execution. Reuse existing purpose, metadata and
code. Preserve the requested source scope, including full-directory scans. If
execution needs a smaller scope, agree on it rather than silently sampling.

## Environment and purpose

Use the project's installed environment and CLI help. Verify package locations
when commands differ from this workflow. For local development, use the requested
Biotope and croissant-baker checkouts. Graph checks and builds need `biotope[graph]`;
Pyright needs Node.js on PATH or `pyright[nodejs]`.

Run commands from the project root. Initialize metadata tracking only when needed
with `biotope init . --no-prompt`; `--no-git` is supported. Scaffolding alone needs
no initialization. Keep raw data and existing purpose files in place.

Read existing purpose files and `biotope map --show` in an initialized project.
Capture agreed intent with `biotope map --purpose "..." --entity "..." --relation "..."`:
purpose replaces the statement; entity/relation flags append and are repeatable.
Update only what changed. Source structure cannot establish research purpose;
ask about missing scientific decisions and resolve routine engineering choices.

## Describe and curate

Reuse completed scans. Run `biotope add <data-path> --json` for new inputs and
review its per-file outcomes, warnings and failures. Baking reads payload bytes,
including checksums; avoid scanning environments or previous outputs. Inspect
declared fields and exact IDs with `biotope map inspect <manifest> --json`.
Inspection reads metadata only and provides no value preview.

Keep unsupported inputs and partial descriptions visible. When evidence supports
a correction or authored description, save it under `graph/metadata/` if a graph
workspace exists, or `.biotope/reviews/` for metadata-only work. Register it with:

```bash
biotope source register <file> --name <managed-name> --reason "<evidence and gaps>"
```

Use `--replace` only after comparing against the current managed description,
including curation notes. The command reports removed structure but replaces the
file without merging or pausing; changed values also need review. Never invent
fields to satisfy a mapping or infer a working loader from metadata.

Curated and annotated descriptions block rebaking. Use
`biotope add <data-path> --bake-to <new-review-file.jsonld>` to inspect a fresh bake
before reconciling it. Put the new file in the review location above, outside the
input and managed `.biotope/datasets/` directories. Preserve curation protection.

## Scaffold and author

For graph work, run `biotope graph scaffold` from the project root, or reuse an
existing `graph/`. Read its `README.md` and the
[typed authoring reference](references/mapping.md). Keep graph code, dependencies,
curation drafts, notes, helpers and outputs inside `graph/`; create extra files
only as needed. Effective managed metadata stays in `.biotope/datasets/`.

The scaffold's `_example` files are inactive patterns, not project data or a
working graph. Adapt them to the purpose and remove unused examples. Generate
actual source types separately from reviewed metadata:

```bash
biotope source generate <manifest> --out graph/sources/<source>/schema.py
```

This generates `schema.py` and creates missing sibling `SOURCE` registration and
loader files. It preserves authored siblings. Do not edit or format generated
modules, copy boilerplate by hand, or transcribe the generated record inventory.
Review new record sets, opaque shapes and nullability when regenerating.

Author topology, loaders, mappings and pipeline composition using the public
`biotope.graph` contracts. Loaders use established format libraries; mappings
transform typed values without opening files. Register selected `SOURCES`,
`TOPOLOGY` and `MAPPINGS` in their folders' `__init__.py` files. Complete the
pipeline's scope, settings, policies and requirement bindings or deferrals.
Python definitions are authoritative; YAML mappings and the old wizard are retired.

## Check and build

Run `biotope graph check graph.pipelines.build_graph:PIPELINE --json`. Include all
relevant generated and authored Python in `Pipeline.code_paths`. Checks import
declarations, so imports must not open payloads or execute pipelines. Resolve
diagnostics and review purpose/placeholder warnings; do not suppress them with
`Any`, blanket ignores or invented metadata.

When graph execution is requested, state the selected inputs, output grain,
identity decisions and expected spot checks, then build into a new run directory:

```bash
biotope graph build graph.pipelines.build_graph:PIPELINE --out graph/build/review-1
```

Biotope supplies the BioCypher file exporter and derives its schema from topology.
Do not add a project adapter or hand-written export schema. Review output values,
counts and provenance using the [reliability boundaries](references/reliability.md)
before reporting acceptance. Scientific graph acceptance is manual; keep any
automated checks focused on project behavior that needs protection.

After metadata changes, regenerate affected contracts and repair authored code;
after code changes, rerun relevant checks. Build again only within the requested
execution scope. During requested cleanup, remove or archive disposable run
outputs; preserve raw data, curated metadata and authored code. Do not use
`biotope rm raw` for test cleanup.

Queue states do not certify graph validity. Use normal Git to version authored
Python alongside metadata. New Baker handlers, database import/querying and paper
evaluation remain separate tasks.
