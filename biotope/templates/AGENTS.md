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

Generate source contracts with `biotope source generate <manifest> --out graph/sources`,
where `<manifest>` is the registered `.biotope/datasets/<name>.jsonld`, never a
draft under `graph/metadata/`; do not edit generated modules. **One record set
becomes one source package**, at `graph/sources/<name>/<record-set>/`, the folder
named for the manifest's filename. One manifest describing a whole directory
still yields one folder per record set, so one upstream file can be added,
removed or re-encoded on its own. A directory-level bake is expected;
do not split the Croissant to get separate packages. The command creates missing
sibling registration and loader files and a generated `CONTRACTS` inventory per
manifest; select from it into `SOURCES`. Implement each loader with established
format libraries, sharing a helper only where decoding genuinely repeats;
regeneration preserves authored siblings and never deletes an orphaned package.
Python dataclasses define the topology; stable `schema_id` values identify concepts
independently of module names. Each node uses a separate identifier NewType, and
edge endpoints use the corresponding node ID types. Python mappings transform
typed values without file access; each takes named `SourceRecord[...]` parameters
and declares its outputs in the return annotation, so composition is checked
statically. A source row may map straight to topology objects. Add a separate
normalization mapping producing an intermediate only when sources must converge,
a stage needs buffering or aggregation, or one normalization feeds several graph
mappings. The old YAML engine and wizard are retired.

Fill `TOPOLOGY`, `SOURCES` and `MAPPINGS` in their folders' `__init__.py` files;
the explicit `Pipeline` imports those registries. State scope,
identity rules, join cardinality, unmatched policies, output grain and expected
spot checks. Keep source evidence alongside records. Current intent lists are
requirements; bind them to concepts or explicitly defer with reasons.

Describe every concept and property where it is declared: whoever queries the
finished graph receives labels and values and nothing else. Declare in
`graph/query_context.py` the question families this graph claims to answer and
every rule needed to filter, join or compare — selection, statistic definitions,
identity conditions, qualifiers and stated uncertainty. Declare in
`graph/checks.py` the validation checks that decide whether those claims hold,
each with an expectation read from the source rather than recomputed from the
pipeline. Record an audit in every stage that selects, joins or aggregates, and
never let a record be dropped by a bare `continue`: report it through
`context.exclude(...)` or account for it in an audit. A build with no checks is
reported as unverified, and that is the honest description of it.

`biotope graph check --json` checks definitions and Python types.
Use `--graph <folder>` to select another workspace and package-relative imports
for portability. Inputs resolve relative to its parent. Imports must not open
payloads or execute loaders/mappings. When the task includes
construction, `biotope graph build --out graph/build/<run>` invokes
project loaders and uses Biotope's exporter to write BioCypher files, provenance
and a run record. No project-specific BioCypher adapter is needed. Inspect
values and source traces before claiming acceptance. Failed runs are incomplete.

`biotope graph quality --json` executes the declared scope once without export;
its latest assessment is in `graph/reports/quality.json`. Review advisory counts,
missing properties, connectivity, endpoint concentration and self-loops without
claiming scientific acceptance. Quality and build each execute the pipeline.
`biotope graph metagraph` views topology independently; `--json` writes no HTML.
Add `--report <quality.json-or-run.json>` for matching-topology observations.
Unrun measurements remain unmeasured; illustrative examples are bounded.

`run.json` reports `validation` per check and per capability: a failed check
blocks the export, an unverified one leaves its capability unresolved while the
rest stays usable. Read the generated `query_context.json` the way its consumer
will — with the graph and that document alone — before claiming acceptance.

Use normal Git to version authored Python. Biotope's status/annotation/tracking
commands remain available; queue states do not certify graph validity. Preserve
raw data, curated metadata and authored source/topology/mapping/pipeline code during
cleanup. Archive only run outputs. Database import, querying and new format readers
are separate work.
