# Agent instructions for this Biotope project

Use Biotope to describe and curate source metadata, capture research requirements,
and maintain typed Python graph definitions. Read the biotope-croissant skill for
the workflow and public contracts. Keep the user's existing purpose and scientific
choices; ask about missing decisions without blocking routine engineering work.

Use the installed environment. During local integration, install the local baker
and `biotope[graph]` together. Describe selected data with `biotope add`; inspect
its Croissant metadata with `biotope map inspect`. Reuse existing scans and account
for omissions. Baking/checksums read bytes; structural inspection has no row samples.

Author evidence-based Croissant corrections in a separate file and register them
with `biotope source register --name ... --reason ...`. Use `--replace` after review.
Registered corrections block rebaking; reconcile separately rather than removing
the protection. Never invent structural metadata or modify raw data to pass checks.

Initialization, baking, graph scaffolding and execution are independent steps;
perform the ones requested. For graph authoring, run `biotope graph scaffold`
from the project root, or reuse an existing `graph/`. Keep graph code, dependency
configuration, corrections, tools and outputs there. Use the supplied boilerplate
for mechanics; use the purpose and evidence to choose topology and transformations.
Read `graph/README.md` for the inactive `_example` patterns. Generate actual source
contracts separately; do not register illustrative metadata as project data.

Generate `graph/sources/<source>/schema.py` with `biotope source generate`; do not edit
it. The command creates missing sibling registration and loader files; generated
`RECORDS` keeps the class inventory current. Implement the loader with established
format libraries; regeneration preserves authored siblings.
Python dataclasses define the topology; stable `schema_id` values identify concepts
independently of module names. Each node uses a separate identifier NewType, and
edge endpoints use the corresponding node ID types. Python mappings transform
typed values without file access. The old YAML engine and wizard are retired.

Fill `TOPOLOGY`, `SOURCES` and `MAPPINGS` in their folders' `__init__.py` files;
the explicit `Pipeline` imports those registries. State scope,
identity rules, join cardinality, unmatched policies, output grain and expected
spot checks. Keep source evidence alongside records. Current intent lists are
requirements; bind them to concepts or explicitly defer with reasons.

`biotope graph check graph.pipelines.build_graph:PIPELINE --json` checks definitions and Python types.
Imports must not open payloads or execute loaders/mappings. When the task includes
construction, `biotope graph build graph.pipelines.build_graph:PIPELINE --out graph/build/<run>` invokes
project loaders and uses Biotope's exporter to write BioCypher files, provenance
and a run record. No project-specific BioCypher adapter is needed. Inspect
values and source traces before claiming acceptance. Failed runs are incomplete.

Use normal Git to version authored Python. Biotope's status/annotation/tracking
commands remain available; queue states do not certify graph validity. Preserve
raw data, curated metadata and authored source/topology/mapping/pipeline code during
cleanup. Archive only run outputs. Database import, querying and new format readers
are separate work.
