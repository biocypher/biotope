# Typed engine review decisions

This record was reconstructed on 9 September 2026 from the retained tests,
local evidence and the independent [second review](spec2_review2.md). The original
disposition file was missing. Its findings were reproduced in the second
review's [first-review checks](spec2_review2_sidenotes.md#first-review-fixes-as-reproduced).

## First review

| Findings          | Disposition and retained evidence                                                                                                                                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1, F4, F5        | Fixed generated-module/checker complexity and opaque-type detection. The 55 × 200-field regression uses strict Pyright in [source tests](../../tests/graph/test_sources.py).                                                                 |
| F2, F3            | Preserved annotation protection, added a separate review-bake route, and separated structural freshness from bookkeeping changes. Covered by source/revision and annotation tests.                                                           |
| F6, F7            | Fixed export labels and verified scalar/list escaping against the pinned BioCypher writer in [output tests](../../tests/graph/test_output.py).                                                                                               |
| F9, F10           | Recorded installed/editable software identity and preserved file permissions during atomic writes. Covered by the example and source tests.                                                                                                  |
| F11, F14          | Retired unused acquisition code and bounded exclusion evidence. Manual queue tracking remains; [runtime tests](../../tests/graph/test_runtime.py) cover exclusion reporting.                                                                 |
| F8, F12, F13, F15 | Retained by decision, as recorded in the second review. Mapping-call evidence, explicit requirement references and copying emitted values remain intentional. A new purpose schema and property-level lineage remain outside this iteration. |

The second review independently reproduced these fixes. Its deferred performance
and housekeeping findings remain in [the sidenotes](spec2_review2_sidenotes.md);
they do not justify expanding this implementation.

## Second review

| Finding                              | Resolution                                                                                                                                                                                                                                                                                                                            |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Workbook runbook gap              | Documented the current local Baker's Excel skip and the exact managed name for registering a reviewed workbook description. No new reader or handler.                                                                                                                                                                                 |
| 2. Missing evidence and stale counts | Restored this record and the [historical real-data summary](02-typed-graph-engine.real-data-check.md) from available evidence. The spec distinguishes current checks from historical results and links the archived spec 1 runbook.                                                                                                   |
| 3. Competing layouts                 | The worked example now uses the scaffold's `SOURCES`, `TOPOLOGY` and `MAPPINGS` registries and package-relative imports. Its test copies the example directly and verifies those registrations; it no longer overlays two layouts. Topology concept directories are regular packages in both.                                         |
| 4. Incomplete source setup           | Generated modules expose top-level `RECORDS` and a `SourceRow` union. The CLI creates missing registration/loader files; regeneration preserves authored files and imports the current inventory. Global source selection stays explicit. A deliberate record subset remains valid rather than being rejected as incomplete coverage. |
| 5. Unstated purpose and placeholders | Definition checks warn when intent is absent, purpose is blank, requirements are empty, or registered concept IDs use `example:`. Warnings appear in human output and JSON. These remain warnings: independent authoring and the illustrative example are supported.                                                                  |
| 6. Silent metadata loss              | Before explicit replacement, report missing top-level keys, record-set IDs, nested field IDs and curation-note keys. Preserve notes supplied in incoming metadata. The command still replaces; it does not merge, infer reconciliation, or add a confirmation workflow. Changed values and nested annotations still require review.   |

The generator format is now version 3. Regenerate existing source modules with
the documented command; keep authored loaders and registrations. The Python API
`generate_source` remains a single-module operation; the CLI's
`generate_source_package` adds source setup.

Current verification and remaining B9 acceptance are tracked in the
[canonical spec](02-typed-graph-engine.spec.md#readiness-evidence).

Self-review also caught Pyright's parse-depth limit when `SourceRow` chained
337 classes with `|`. Flat `Union[...]` preserves the same type information and
passes on the saved Open Targets metadata. The source-setup regression now
covers this size and regeneration without adding another test case.
