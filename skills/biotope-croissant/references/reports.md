# Reading checks and run reports

Use this reference while resolving findings and reviewing a build's claims.

## Validation boundaries

| Layer               | Establishes                                                                           | Limitation                                            |
| ------------------- | ------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Source metadata     | The structure declared by a description                                               | Does not establish completeness or loadability        |
| Definition check    | Contracts, topology, requirement bindings, interpretation references and Python types | Does not execute loaders or inspect source values     |
| Runtime integrity   | Loaded types, object consistency and resolved endpoints                               | Does not decide which records should have been loaded |
| Quality             | Counts, missing properties, connectivity, endpoint concentration and self-loops       | Measures only emitted objects                         |
| Declared validation | Agreement with the project's stated expectation                                       | Covers only the cases the check implements            |

Static types do not establish biological equivalence. A failed build remains
incomplete even if it produced some files. Use expectations derived independently
of the pipeline to detect eligible records that were omitted.

## Read the run record

| Field in `run.json`             | Review it for                                                            |
| ------------------------------- | ------------------------------------------------------------------------ |
| Completion and findings         | Whether the operation finished and which steps failed                    |
| `validation.state`              | `passed`, `failed`, `unverified` or `absent`                             |
| `validation.capabilities`       | Per-capability `supported`, `unverified`, `failed` or `unchecked` states |
| `validation.checks[].evidence`  | The source of each expectation                                           |
| `audits`                        | Stage input/output grains, selection rules and named counts              |
| Findings with `kind: exclusion` | Policy counts and bounded evidence                                       |
| `exporter`                      | Verified writer version and physical format                              |
| `query_context`                 | Interpretation guidance accompanying the graph                           |

`failed` blocks export. `unverified` leaves the associated capability unresolved.
`unchecked` means a capability has no bound check; `absent` means no validation
checks were declared. `supported` means the bound checks passed, within their
stated scope.

## Quality observations

Quality reads validated Python objects before export. Empty required concepts,
wholly missing properties and self-loops warn. Connectivity and endpoint
concentration are observations. Empty denominators remain unmeasured; zero and
`False` are usable values. Failed execution leaves later measurements unrun.

`biotope graph quality --json` saves the latest assessment, including failures,
to `graph/reports/quality.json` without exporting. Quality and build each execute
the pipeline once; running both executes twice.

## Export and provenance

The exporter checks the installed BioCypher version before reading payloads.
`BioCypherWriter("csv")` writes data and header CSVs; `BioCypherWriter("parquet")`
writes Parquet without CSV headers and requires a compatible database importer.
Biotope checks the output against the declared format after writing.

Each mapping call attaches its input contributors to its outputs. This is
record-level attribution, not per-property lineage. Exclusions retain counts and
at most ten evidence references per policy, with a truncation flag. Audits retain
stage descriptions and named counts; they do not hold that evidence sample.
Property examples contain up to three distinct non-null values in encounter order.
Keep these limits visible when summarizing a report.

`biotope graph metagraph` loads topology independently of the pipeline.
`--report <file>` overlays observations from a matching assessment without rerunning it.
