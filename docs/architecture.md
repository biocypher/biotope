# Architecture

Biotope separates source description, graph authoring and execution. Croissant
metadata records what is known about a source; Python code defines how selected
records become graph objects.

```text
Local data ── croissant-baker ── reviewed Croissant ── generated source classes
    │                                                          │
    └── project loaders ── typed records ── mappings and joins ──┤
                                                               ↓
                                          validated graph → BioCypher files
```

## Responsibilities

| Component           | Responsibility                                                               |
| ------------------- | ---------------------------------------------------------------------------- |
| `biotope.commands`  | CLI orchestration, project metadata and Git operations                       |
| `biotope.croissant` | Croissant models and metadata inspection                                     |
| croissant-baker     | Format-aware local source description and scan diagnostics                   |
| `biotope.graph`     | Source generation, typed contracts, checks, execution and export             |
| Project `graph/`    | Source readers, topology, transformations, selection and research validation |
| BioCypher           | Writing the graph files used for database import                             |

The project owns identities, units, null handling, join cardinality and exclusions.
Biotope supplies contracts for recording and checking those decisions. It does not
infer biological equivalence or decide which records answer a research question.

## Metadata and source records

`biotope add` reads local files and stores Croissant descriptions under
`.biotope/datasets/`. Curated descriptions and saved annotations are protected
from rebaking. A fresh description can be written separately for reconciliation.

`biotope source generate` reads a reviewed manifest and creates one package per
top-level record set. Generated dataclasses describe the values a loader supplies.
They contain references to Croissant fields; the metadata document retains
extraction rules and descriptions. Generation neither reads rows nor supplies a reader.

A project loader returns `SourceRecord` values with source evidence. Mappings
accept these typed records and return intermediate records or topology objects.
Ordinary Python composes loaders, joins and transformations into a `Pipeline`.

## Checks and execution

`biotope graph check` imports declarations, checks source freshness and requirement
bindings, and runs Pyright. It does not invoke loaders or mappings. Project modules
must therefore avoid reading data or executing work during import.

`biotope graph quality` and `biotope graph build` each check and execute the
selected pipeline once. They validate source values, emitted objects, identity
conflicts and endpoint references, then run declared research checks. Quality
saves an assessment without exporting; build also writes BioCypher files.

Biotope retains graph objects and contributor references in memory. Projects
should select a scope that fits the available resources. Streaming source readers
do not make the accumulated graph disk-backed.

## Output and review

A build writes graph files, derived topology and export schema, provenance,
interpretation guidance and `run.json`. The run record identifies source metadata,
code, dependencies, settings, exclusions, audits and validation outcomes.

Provenance follows mapping inputs: it records contributing rows or containers,
without inferring which input determined each property. Declared validation checks
can compare the graph against independently established expectations. Built-in
quality observations describe the emitted population and cannot detect every
omission from that population.

`biotope graph metagraph` loads topology independently and writes an offline
viewer. An existing quality or build report can add observations without rerunning
the pipeline. Database import and querying are separate steps.

See [typed graph projects](mapping.md) for authoring,
[technical notes](mapping_sidenotes.md) for detailed contracts, and
[development ideas](ideas.md) for possible future work.
