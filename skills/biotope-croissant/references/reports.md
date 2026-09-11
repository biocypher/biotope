# Reading the checks and the run

Read this at step 6 while resolving findings, and at step 7 before claiming a capability holds.

## Each layer establishes one thing

| Layer             | Establishes                                                                                       | Cannot see                                     |
| ----------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Source metadata   | The structure a description declares                                                              | Whether it is complete, correct, or loadable   |
| Definition check  | Contracts, topology, requirement bindings, interpretation references, Pyright over `code_paths`   | Anything about values; it never executes `run` |
| Runtime integrity | Loaded values validated without coercion, conflicting IDs rejected, every edge endpoint resolved  | Whether the right records were loaded          |
| Quality           | Counts, missing properties, connectivity, endpoint concentration, self-loops over emitted objects | Any record the pipeline never emitted          |
| Validation check  | The graph against an expectation derived outside the pipeline                                     | Only what the project chose to check           |

A green definition check does not establish uniqueness, namespace compatibility or biological equivalence. A type conversion and a shared column name are not scientific evidence. A failed build is not a completed graph, even when files were written.

## Only validation checks compare the graph with anything outside it

Every layer above them measures what was emitted, so none can notice a record the pipeline never produced. A run with no validation checks reports `validation.state: "absent"`. That is a finding about the build, not a formality.

## Read a run in this order

| Field in `run.json`               | Read it for                                                          |
| --------------------------------- | -------------------------------------------------------------------- |
| `validation.state`                | `passed`, `failed`, `unverified` or `absent` — `absent` is not clean |
| `validation.capabilities`         | Per capability: `supported`, `unverified`, `failed`, `unchecked`     |
| `validation.checks[].evidence`    | Where each expectation came from                                     |
| `audits`                          | Each stage's grains, admission rule and counts                       |
| `findings` with `kind: exclusion` | Declared policy counts and bounded evidence                          |
| `exporter`                        | The writer version and physical format actually verified             |
| `query_context`                   | Exactly what a consumer with only the graph receives                 |

`failed` blocks the export. `unverified` records missing knowledge: that capability stays unresolved while the rest of the graph remains usable. `unchecked` means a capability was claimed and nothing tests it.

## Quality measures what was emitted, not what should have been

It reads validated Python objects before export, never the BioCypher files and never the sources. Empty required concepts, wholly missing properties and actual self-loops warn. Connectivity and endpoint concentration are observations, not failure criteria. Empty denominators stay unmeasured, and zero and `False` are valid values. Failed execution leaves every later measurement unrun.

`biotope graph quality --json` saves the latest assessment, including failures, to `graph/reports/quality.json` and stops before export. A complete quality report does not mean a graph was exported. Quality and build each execute the pipeline once, so run both only when the second execution serves the request.

## The exporter is verified before any payload is read

Escaping, file naming and the physical format belong to one writer release rather than to the BioCypher API, so an unsupported version is refused up front with the install command for the tested one. After writing, the export directory is checked against the same contract. Install the version the error names.

## Bounded samples are not complete lists

Mapping calls attach every input contributor to each output; that is not per-property lineage. Exclusions and audits keep counts plus at most ten evidence references, with a truncation flag. Illustrative property examples are up to three distinct non-null values in encounter order. Do not present any of these as exhaustive.

`biotope graph metagraph` inspects registered topology without importing the pipeline, and with `--report` overlays a matching assessment.
