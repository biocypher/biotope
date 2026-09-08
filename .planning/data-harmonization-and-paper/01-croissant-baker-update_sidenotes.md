# Croissant-baker integration — technical notes

Supporting evidence for the [specification](01-croissant-baker-update.spec.md). These notes describe inspected code and data inventories; they are not test results. Recheck the baseline during implementation. The specification defines scope and acceptance.

## Dependency baseline

At inspection, Biotope was `0.8.0` at `9465817` on `feat/dataset_harmonization`. It declared `croissant-baker>=0.3,<1` and an editable `../croissant-baker` uv source. Baker was clean at `3c11839` on `integration/all-format-handlers`, with the SOFT, OME, HDF5, and spreadsheet branches locally merged. Its version remained `0.3.2`; upstream merge and release status were not verified.

Biotope already has compression-aware metadata models, progress/warning reporting, and scan-coverage summaries. Existing edits to `.gitignore`, `biotope/commands/add.py`, and `tests/commands/test_add.py` predate this task. Recheck revisions and working-tree state when implementation begins.

At the planning baseline the directory was Git-ignored. It is now untracked after an external working-tree change; these local documents still do not travel with a branch automatically; provide them explicitly to another checkout or delegated agent. Keep the lead's copy as the progress record.

Installing Biotope and baker as unrelated command-line tools does not establish that Biotope imports the local baker. Verify both package locations in the interpreter used by the Biotope CLI.

## Format coverage to exercise

| Format | Local baker description | Limit to retain in diagnostics and interpretation |
| --- | --- | --- |
| Excel `.xlsx/.xlsm/.xls` | Columns/types for readable sheets | One table per sheet; cached formula values; no executable field extraction instructions. |
| GEO `.soft` | Entity attributes, characteristic keys, and table structures | Names/types rather than a general API yielding metadata values. |
| HDF5 `.h5/.h5ad/.hdf5` | Recognized AnnData/10x layouts or bounded structural inventory | Some container sections are omitted; structural description is not matrix loading. |
| OME-TIFF | Separate `ome_images` collection and OME header fields | File-level records use the first OME image's Pixels fields; header fields lack extraction instructions. |
| Compression and archives | `.gz/.bz2/.xz` wrappers for most handlers; unopened archives are recorded | Checksums still read complete files. Zipped Zarr remains unsupported. |

Existing CSV/TSV, JSON, Parquet, and ordinary image descriptions remain part of the test baseline.

## Integration findings

- **Single-file assembly:** directory ingestion uses baker's full assembly, while single-file ingestion constructs a record set from top-level `column_types`. That path loses the richer workbook/HDF5 structures.
- **Record-set identity:** different workbooks can have sheets with the same name. Baker supplies distinct record-set IDs, while Biotope looks up record sets by name. Exercise this case rather than assuming model parsing proves correct selection.
- **Pipeline wording:** Biotope infers `processed` from the presence of fields. Messages should distinguish available structure from executable data access.
- **Model versus reader support:** `FileSet.includes` accepts lists, but the existing custom row reader treats them as a single path. Wrapped suffixes also miss its explicit reader branches. These findings identify the duplicated reader boundary; they are not requirements to expand it.
- **Shared dependency:** inspection, mapping previews, the wizard, and generated graph adapters reference `AcquisitionContext`. Remove the custom reader without designing a graph-loading replacement. Eager CLI imports and shared APIs may need to be separated so dangling downstream code cannot break the supported commands.

## Removal and validation references

`get` downloads raw data; `search` uses `biotope/registry/` to search BioContext and bio.tools; `discover` calls `discover_sources` in `biotope/croissant/api.py` and uses `biotope/croissant/registry/`. The last API module also contains retained mapping helpers, so deleting its discovery function must not discard the entire module. Follow imports and defaults to remove the dedicated feature code while preserving shared functionality.

`read` is a text-echo placeholder. `annotate load` is a separate source-record loading path through the `mlcroissant` CLI; it does not use `AcquisitionContext` but is also being removed. `annotate validate` uses `mlcroissant validate`; verify that retained metadata validation does not load source records.

The current mapping preview combines structural findings and a projected schema with sample node/edge execution. Keep the structural checks and summary; remove sample execution and its dependencies. `project_model.py` holds purpose and entity/relation lists, while detailed target choices remain in mapping definitions. Their representation is unchanged in this iteration.

The existing CI test command is `uv run pytest tests/ -v`. Use focused subsets during TDD and run the retained suite at handoff. The specification requires a complete-suite bloat audit and pruning. Retire tests solely for deleted or unsupported downstream features instead of repairing graph functionality for them; preserve checks for retained behavior from mixed tests. Record collection failures in the audit and resolve them for the retained suite.

Baker's handler contract separates `claims(source)`, `extract(source)`, and `build_croissant(...)`. `extract` returns structural metadata. Shared `FileSource` methods open decompressed bytes/text; there is no supported common API for rows, arrays, or other values. A future reusable reader API belongs in baker and is not a prerequisite for metadata integration.

## Data locations and manual checks

**Daria:** `/Users/vlad/Projects/virtual-human-dev/daria_mvp/data` contains context workbooks/notes, screening artifacts, and raw data for GSE280315, GSE311609, GSE327347, and GSE335275. Bounded filename listings showed SOFT, CSV/JSON/Parquet (often compressed), HDF5, TIFF/OME-TIFF/BTF/PNG, and zipped Zarr. Some compressed images are several gigabytes. Raw payloads and archives were not opened during this planning inspection.

The [consulting brief](/Users/vlad/Projects/virtual-human-dev/biotope/.planning/data-harmonization-and-paper/data-harmonizaton.md) motivates study/sample metadata harmonization, technical-method tables, provenance, uncertainty, and retained inclusion/rejection decisions. Its August dates and readiness statements are historical context. Bulk acquisition and preprocessing are outside its original MVP.

**INTRAC:** `/Users/vlad/Projects/virtual-human-dev/biotope-bench/data/intrac_260731/workspace/raw` contains differential-expression CSVs, an ortholog table, `study_metadata.xlsx`, notes, and supporting papers. The corpus root contains `purpose.txt` and `DATASET_NOTES.txt`. Use the purpose to orient mapping; it does not turn this integration test into a full scientific analysis.

For in-place runs, choose the root deliberately, use `biotope init . --no-prompt` only for a new project, and resume existing projects. Directory `add` writes managed manifests and a `.biotope.yaml` sidecar. Add selected input paths rather than the entire working directory. Copy the whole skill directory: its relative `references/` files are required.

## Code references

- [Biotope dependencies](/Users/vlad/Projects/virtual-human-dev/biotope/pyproject.toml), [ingestion](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/commands/add.py), [pipeline state](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/metadata.py:163), [manifest model](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/croissant/spec.py:187).
- Former custom acquisition reader: `biotope/croissant/acquisition/context.py` (removed in this implementation); [inspection](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/croissant/mapping/inspector.py), [mapping preview](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/croissant/mapping/preview.py), [generated adapters](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/croissant/scaffold/materialize.py:157), [layout tests](/Users/vlad/Projects/virtual-human-dev/biotope/tests/croissant/test_baker_layout.py).
- [CLI registrations](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/cli.py), [shared mapping/discovery API](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/croissant/api.py), [annotation loading/validation](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/commands/annotate.py), [purpose model](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/project_model.py).
- [Handler contract](/Users/vlad/Projects/virtual-human-dev/croissant-baker/src/croissant_baker/handlers/base_handler.py:120), [shared file opening](/Users/vlad/Projects/virtual-human-dev/croissant-baker/src/croissant_baker/sources.py), [format table](/Users/vlad/Projects/virtual-human-dev/croissant-baker/docs/_generated/formats-table.md), [format limitations](/Users/vlad/Projects/virtual-human-dev/croissant-baker/docs/user-guide/supported-formats.md).
