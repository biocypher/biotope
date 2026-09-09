# Historical real-data checks: 8 September 2026

Restored on 9 September from the saved artifacts under
`evidence/typed-engine/real-data-2026-09-08/`. These are historical engineering
checks, not a new run or scientific acceptance of the consulting graphs. Current
source contracts require regeneration after generator changes.

## Metadata scope

| Project      | Saved evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Daria        | All 30 saved manifests generated successfully: 206 record sets, 1,629 fields. See [generation results](evidence/typed-engine/real-data-2026-09-08/daria/generation-result.json).                                                                                                                                                                                                                                                                                   |
| INTRAC       | The historical bake scanned 29 files: 22 described, 7 unsupported. It yielded 22 record sets and 307 fields. See [bake log](evidence/typed-engine/real-data-2026-09-08/intrac-bake.log) and [generation results](evidence/typed-engine/real-data-2026-09-08/intrac/generation-result.json).                                                                                                                                                                        |
| Open Targets | The bake described all 1,632 Parquet files, yielding 337 record sets and 4,003 fields. Generation also checked the separate authored description with 56 record sets and 1,099 fields; those counts overlap and must not be treated as additional unique source coverage. See [bake log](evidence/typed-engine/real-data-2026-09-08/opentargets-bake.log) and [generation results](evidence/typed-engine/real-data-2026-09-08/opentargets/generation-result.json). |

All generated modules passed the strict checker in that environment. The current
local Baker lacks Excel/HDF5 handlers, so the historical INTRAC coverage does not
predict a fresh scan's result today. The runbook documents the current workbook
fallback.

## Selected value checks

| Project      | Bounded result                                                                                                                                                                           |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Daria        | 50 cell records produced 51 nodes and 50 edges; selected CSV values and 101 provenance records verified.                                                                                 |
| INTRAC       | 24 input records produced 24 nodes and 15 edges; selected CSV values and 39 provenance records verified. A scratch metadata correction for the mixed PMID field was required.            |
| Open Targets | The selected association/target join produced 101 nodes and 100 edges with 201 provenance records. Matching loaded 125,785 source records; this was not a complete graph of the release. |

The saved [output verification](evidence/typed-engine/real-data-2026-09-08/output-verification.json)
records matching repeat graph digests and checked values for all three projects.
[Payload-absent results](evidence/typed-engine/real-data-2026-09-08/payload-free-result.json)
show definition checks passing with source paths replaced by an absent prefix.
The input selection and expected values remain in each project's `probe/`
directory; verification scripts are in the sibling `scripts/` directory.

These checks do not settle identity choices, scientific usefulness, completeness,
duplicate-header interpretation or opaque data structures. B9 remains Vlad's
manual review. The artifacts are local evidence, not installed package files or
a permanent full-dataset test harness.
