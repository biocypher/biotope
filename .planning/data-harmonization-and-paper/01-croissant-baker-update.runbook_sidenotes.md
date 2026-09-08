# Runbook evidence and notes

Use the [runbook](01-croissant-baker-update.runbook.md) for commands. This file
records the earlier sample checks and details useful when investigating a
discrepancy. These results do not establish full-directory acceptance.

## Earlier execution: 8 September 2026

The implementer scanned eight Daria files and seven INTRAC files, independently
spot-checked structure and authored five example mappings. These were integration
examples, not complete scientific mappings. Vlad subsequently requested testing
the whole Daria `raw` directory and reported that progress worked after a silent
startup. Full-scan review and his Claude Code checks remain pending.

| Dataset | Selected inputs                                                                                                       | Observed result                                                                                          |
| ------- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Daria   | Context workbook; GSE327347 SOFT, 10x HDF5 and cell Parquet; GSE280315 JSON, probe CSV and PNG; GSE335275 zipped Zarr | 8 files, 2,626,498 bytes; 7 described, including a partial workbook; 1 unopened archive. 15 record sets. |
| INTRAC  | Hill and Kaiser expression CSVs, mouse DE CSV, human/mouse ortholog CSV, study workbook, notes and one PDF            | 7 files, 31,154,527 bytes; 5 described; 2 without handlers. 5 record sets.                               |

Exact input lists and output logs:
[Daria inputs](evidence/daria/inputs.txt), [Daria output](evidence/daria/add.txt),
[INTRAC inputs](evidence/intrac/inputs.txt), [INTRAC output](evidence/intrac/add.txt).
Other samples, large images and several large INTRAC tables were not part of
that execution. Use the full-directory commands in the current runbook for the
next review.

The run used Python 3.12.13, local Biotope 0.8.0 at `9465817` with the working-tree
implementation, and local baker 0.3.2 at `3c11839`. The
[dependency evidence](evidence/dependency-baseline.txt) records import paths and
revisions. Baker's version string alone does not identify the new handlers;
install both editable checkouts into the same interpreter.

## Structural checks and mappings

The [external spot-check script](evidence/spot-check-structure.py) compares known
headers, workbook sheets, Parquet schemas, HDF5 paths/shapes and image headers.
It is independent of Biotope and covers only the fixed sample selection. Running
it rewrites the sample-check logs; it is not necessary for the current runbook.
Results: [Daria](evidence/daria/independent-structure.txt) and
[INTRAC](evidence/intrac/independent-structure.txt).

All selected payload hashes matched before and after execution:
[Daria before](evidence/daria/sources-before.json) /
[after](evidence/daria/sources-after.json),
[INTRAC before](evidence/intrac/sources-before.json) /
[after](evidence/intrac/sources-after.json).

Five example mappings passed structural checks:

- Daria: [study workbook](evidence/daria/mappings/darias_input.mapping.yaml) and
  [10x features](evidence/daria/mappings/GSM9654050_SPATIAL164109_cell_feature_matrix.mapping.yaml).
- INTRAC: [study provenance](evidence/intrac/mappings/study_metadata.mapping.yaml),
  [Hill measurements](evidence/intrac/mappings/hill_af_corrected.mapping.yaml) and
  [ortholog relation](evidence/intrac/mappings/orthologs_human_mouse.mapping.yaml).

Commands and final JSON checks are saved for
[Daria](evidence/daria/mapping-commands.txt) ([JSON](evidence/daria/mapping-preview.json))
and [INTRAC](evidence/intrac/mapping-commands.txt) ([JSON](evidence/intrac/mapping-preview.json)).
Empty stubs are inactive in the existing model; passing checks alone do not
establish purpose coverage. Study-title identities, composite IDs, uniqueness
and transformation semantics need project review.

## Findings

| Finding                                                                                     | Result or limitation                                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Daria workbook has six sheets.                                                              | Baker omitted `Spatial_proteomics_markers`, which is not one standalone table, and named it in the diagnostics. Five sheets and their nonempty headers were preserved.                                                                                                          |
| 10x HDF5 describes a 541 × 6,947 matrix.                                                    | Independent dimensions and axis metadata agree; matrix values and cross-source identity were not checked. SOFT also describes attributes without returning values.                                                                                                              |
| Zipped Zarr, notes and PDF have no structural fields.                                       | Tracked without invented mappings. No archive expansion, Zarr handler or text extraction was added.                                                                                                                                                                             |
| INTRAC Kaiser has an unnamed index column.                                                  | Biotope now accepts baker's declared field ID when a name is absent. Its meaning remains unassigned.                                                                                                                                                                            |
| Single-file drift checks included unrelated project files.                                  | Fixed to follow declared source references using timestamps.                                                                                                                                                                                                                    |
| Numeric properties appeared as strings.                                                     | Direct-field summaries now use declared metadata types. No source values are read.                                                                                                                                                                                              |
| INTRAC notes distinguish prefiltered Hill/Kaiser data from an unfiltered older mouse table. | Preserve this distinction in later analysis; these checks did not assess significance or missing values.                                                                                                                                                                        |
| Progress previously started after baker import and handler initialization.                  | A fresh-process measurement found about 8.7 seconds of silent baker setup. Progress now starts before those operations; counts still arrive when baker completes its first file. See [red](evidence/startup-progress-red.txt) and [green](evidence/startup-progress-green.txt). |

## Operational details

- Use `--rebake` for directory regeneration and `--force` for an individual file.
  Review annotations and mapping references after regeneration.
- A directory produces one manifest plus its `.biotope.yaml` annotation sidecar.
  Single-file manifests mirror the input path, replacing its last suffix with
  `.jsonld`: `family.soft.gz` becomes `family.soft.jsonld`.
- `add` stages metadata in Git. Archiving test outputs does not reset the Git
  index; inspect `git status` before making a commit. Cleanup preserves source
  data and project settings, including purpose.
- Keep `add` attached to the terminal for the progress check. Piping through
  `tee` changes terminal detection and suppresses the live display. Named warnings
  and the preparation/summary messages remain available in redirected output.
- Baking can read large files for checksums even when no handler describes them.
  The earlier small PNG check does not establish large-image performance.
- Workflow states (`raw`, `processed`, `mapped`) describe progress, not scientific
  validity. Manual YAML edits do not automatically update workflow status.

Acceptance and remaining gates are tracked in the
[spec](01-croissant-baker-update.spec.md); automated protection is listed in the
[test audit](01-croissant-baker-update.test-audit.md).
