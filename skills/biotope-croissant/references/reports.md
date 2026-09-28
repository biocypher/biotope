# Reading checks and build reports

Use this reference while resolving findings and reviewing a build's claims.

## Check boundaries

| Layer             | Establishes                                                                                     | Limitation                                                |
| ----------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Manifest          | The structure the Croissant description declares                                                | Does not establish completeness or loadability            |
| Inventory         | Every described input has a package, is selected or excluded, and matches its reviewed revision | Does not say whether an exclusion is scientifically right |
| Definition check  | Contracts, field coverage, terms, topology, requirement bindings, descriptions and Python types | Does not execute loaders or inspect source values         |
| Runtime integrity | Loaded types, closed vocabularies, completed loaders, object consistency and resolved endpoints | Does not decide which records should have been loaded     |
| Quality           | Counts, missing properties, connectivity, endpoint concentration and self-loops                 | Measures only emitted objects                             |

Static types do not establish biological equivalence, and no check compares the
graph with the science it claims. A dropped eligible record passes every layer.
Review-time independent reads, derived from the sources themselves, are the only
way to notice it. A failed build is incomplete even if it produced some files.

## Read the run record

`graph/build/run.json` is `schema_version` 2; Biotope still reads and replaces
version 1 reports.

| Field in `run.json`             | Review it for                                                         |
| ------------------------------- | --------------------------------------------------------------------- |
| `state`, `error` and findings   | Whether the build finished and which stage failed                     |
| `scope`, `policies`, `settings` | The selection the graph embodies and the rules behind every exclusion |
| `definitions.inventory`         | Roots, packages, registered, selected and excluded source counts      |
| `definitions.excluded_sources`  | Each excluded source and its reason                                   |
| `definitions.standardization`   | Term bindings, preserved fields, aliases and missing-value policies   |
| `loaded_records`                | Records read per source                                               |
| `audits`                        | Stage input/output grains, selection rules and named counts           |
| Findings with `kind: exclusion` | Policy counts and bounded evidence                                    |
| `graph_objects`, `graph_digest` | What was exported, and a deterministic fingerprint of it              |
| `exporter`                      | Verified writer version and physical format                           |
| `dependencies`                  | Installed versions of Biotope, its tools and every imported library   |

A failed rebuild leaves the previous build in place and writes
`graph/build/last_failure.json` beside it; the next success removes it. A build
replaces `graph/build/` only when it recognizes every file there.

## Quality observations

Quality reads validated Python objects before export. Empty required concepts,
wholly missing properties and self-loops warn. Connectivity and endpoint
concentration are observations. Empty denominators remain unmeasured; zero and
`False` are usable values. Failed execution leaves later measurements unrun.

`biotope graph quality --json` executes the pipeline without exporting and prints
the assessment; it writes no file. A build records the same measurements in
`run.json`. Quality and build each execute the pipeline once; running both
executes twice.

## Export and provenance

The exporter checks the installed BioCypher version before reading payloads.
`BioCypherWriter("csv")` writes data and header CSVs; `BioCypherWriter("parquet")`
writes Parquet without CSV headers and requires a compatible database importer.
Biotope checks the output against the declared format after writing. Export is
headless: labels are the concept's local name, such as `Gene`, widened only when
two concepts collide.

Every exported node and edge carries `biotope_provenance_id`, a zero-based index
into `provenance.json["records"]`. Each record lists its mapping names and indexes
into `evidence`; each evidence entry names a location and a `sources` entry with
the artifact, its version and the RecordSet. Indexes are local to one build, so
distribute `graph/build/` with the graph. This is record-level attribution, not
per-property lineage. Exclusions retain counts and at most ten evidence
references per policy, with a truncation flag. Property examples contain up to
three distinct non-null values in encounter order. Keep these limits visible
when summarizing a report.

`biotope graph metagraph` loads topology independently of the pipeline and writes
`graph/metagraph.html`. `--report graph/build/run.json` overlays observations from
a matching build without rerunning it.
