# Biotope test audit

The complete suite was reviewed and pruned for the metadata-to-mapping boundary.
Collection fell from **399 to 241 cases**, including parameterized cases. The
ledger records 190 retired or renamed IDs and 32 new or renamed IDs; renaming a
test is not new coverage. There was no deletion quota.

The original environment lacked the updated baker's HDF5 dependency. After
synchronization, all 399 original cases passed. The post-sync transcript also
contains three new removal-contract tests, which intentionally failed; it is
not a clean 402-test baseline. See [baseline collection](evidence/baseline-collection.txt),
[initial run](evidence/baseline-tests.txt), [post-sync run](evidence/synced-baseline-tests.txt),
[retained collection](evidence/retained-collection.txt) and
[retained-suite result](evidence/retained-suite.txt).

## Findings and decisions

No literal always-true/always-false tests or swallowed failures were found.
Several tests had weak assertions that could pass without the advertised
behavior. Assertion inspection was sufficient to identify these; no mutation
framework was introduced. Counts alone do not establish protection.

| Test or explicit group                                                                                                                                                                                                             | Category / decision                   | Reason and retained protection                                                                                                                                                                                                                                                              |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `commands/test_get.py`, `integration/test_get_integration.py`, `commands/test_search.py`, `commands/test_status_mcp.py`, `unit/test_registry.py`, `unit/test_search_ranking.py`, `croissant/test_registry.py`, `unit/test_read.py` | Obsolete / delete                     | Downloading, registry discovery and text extraction are intentionally retired. `integration/test_metadata_workflow.py::test_removed_commands_and_sample_options_are_rejected` protects public removal.                                                                                      |
| `croissant/test_acquisition.py`, `test_selectors.py`, `test_build_runtime.py`, `test_codegen.py`, `test_scaffold.py`; `unit/test_view.py`, `test_biocypher_labels.py`                                                              | Obsolete / delete                     | Tests exercised source-value loading, transformation execution or downstream graph functionality. Retirement is intentional. The fresh-process CLI import test guards the retained boundary.                                                                                                |
| `croissant/test_mapping.py` compile/emission, axis execution and legacy schema rejection cases                                                                                                                                     | Mixed obsolete / delete or rewrite    | Keep model/selector grammar, serialization, scaffolding and metadata checks. `test_deferred_relation_definition_state` replaces the compile-coupled deferral test; `test_map_defer_relation_cli_roundtrip` keeps the public transition. No tuple execution replacement.                     |
| `unit/test_build_cli.py`                                                                                                                                                                                                           | Mixed / split and rename              | Move intent, scaffold alias and alignment output checks to `unit/test_mapping_cli.py`, keeping their test names. Retire build-only cases and the obsolete describe-command assertion.                                                                                                       |
| `croissant/test_alignment.py` merge-adapter test and `test_alignment_model_validates`                                                                                                                                              | Obsolete and trivial / delete         | Graph adapter merging is unsupported; a plain constructor/accessor assertion added little. Keep the three metadata-based alignment proposal scenarios.                                                                                                                                      |
| `croissant/test_baker_layout.py` acquisition and duplicate path-inference tests                                                                                                                                                    | Obsolete and redundant / delete       | Retain `test_spec_accepts_compressed_encoding_formats`. Path anchoring remains in `test_acquisition_locations.py`; richer source-link protection is in real-baker integration tests.                                                                                                        |
| `croissant/test_inspector.py` sample output/missing-payload sample-note cases; `test_preview.py` sample tuple case                                                                                                                 | Obsolete / delete                     | Samples are removed. `test_metadata_to_mapping_and_wizard_with_missing_payloads` proves inspection, scaffold, validation and wizard operation without payloads.                                                                                                                             |
| `croissant/test_inspector.py::test_inspector_json_output_is_stable`                                                                                                                                                                | Trivial / delete                      | Round-tripping primitive JSON checked serialization machinery. Actual CLI JSON structure is asserted in the offline workflow and invalid-binding tests.                                                                                                                                     |
| `system/test_import.py`; `unit/test_cli.py` generic help, isolation and read/build cases                                                                                                                                           | Redundant or obsolete / delete        | Keep `test_cli_version`. `test_cli_import_does_not_depend_on_readers_or_graph_execution` tests a fresh interpreter with forbidden imports; public command and option rejection is checked separately.                                                                                       |
| Root/Git helper tests repeated in `commands/test_add.py` and `unit/test_git_commands.py`                                                                                                                                           | Redundant / delete                    | Retain actual root/no-root and Git/non-Git cases in `unit/test_utils.py::test_find_biotope_root` and `test_is_git_repo`.                                                                                                                                                                    |
| `commands/test_add.py::test_bake_directory_describes_compressed_files`                                                                                                                                                             | Redundant / merge                     | Compression format and source assertions now live in `test_bake_directory_reports_coverage`; real mixed-format integration adds partial/failed/unsupported input checks. Keep single-file tracking/provenance and directory tests for their distinct paths.                                 |
| `commands/test_annotate.py` help/hidden-alias-only cases; `test_annotate_staged.py` duplicate no-project case                                                                                                                      | Trivial and redundant / delete        | Keep actual apply/edit behavior, stage selection and the incomplete-annotation no-project case. `annotate load` test retired with the command.                                                                                                                                              |
| Legacy `sc:FileObject` rejection tests in `commands/test_check_data.py` and `test_mv.py`                                                                                                                                           | Obsolete / delete                     | Old artifact compatibility is outside this iteration. Keep checksum, source resolution, move and rollback behavior.                                                                                                                                                                         |
| `commands/test_check_data.py::test_check_data_valid_file`                                                                                                                                                                          | Weak / rewrite                        | Rename to `test_check_data_detects_changed_file`: test valid bytes and then an actual mismatch, including removal of the fake repair advice. The dataset-relative URL case remains.                                                                                                         |
| `commands/test_validation_patterns.py` default/explicit/remote-cluster helper variants                                                                                                                                             | Redundant / delete                    | `test_set_validation_pattern`, `test_show_validation_pattern`, `test_get_validation_info` and their remote variants cover persisted settings through commands. Keep remote-storage handling as a distinct input form.                                                                       |
| `croissant/test_acquisition_locations.py` string-only variant and pathlib glob composition                                                                                                                                         | Redundant/trivial / merge or delete   | The managed-path positive case now takes a string; other paths use `Path`. Keep managed-directory, missing-directory fallback, standalone and remote cases. Do not test pathlib itself.                                                                                                     |
| `croissant/test_croissant_reader.py` plain record-set getter and separate distribution round-trip                                                                                                                                  | Trivial/redundant / merge or delete   | Distribution assertions moved into `test_load_minimal`. The real-baker duplicate-name test checks meaningful ID/name lookup ambiguity. Keep scalar-type aliases: they are distinct baker metadata contracts, not arbitrary parameter variations.                                            |
| `unit/test_init.py` three separate scaffold/config/pyproject cases                                                                                                                                                                 | Too granular / merge                  | `test_init_default_layout` now checks these artifacts together. Keep existing-project refusal, existing pyproject preservation, visible metadata, Git and optional AGENTS behavior.                                                                                                         |
| `unit/test_git_commands.py` commit success/author/amend and log count/author/since variants                                                                                                                                        | Too granular and weak / merge/rewrite | `TestGitCommands::test_commit_author_amend_and_log_filters` checks real author metadata, amend commit count, and actual filter inclusion/exclusion. Old success-only assertions could not establish those behaviors.                                                                        |
| `unit/test_git_commands.py` biotope-only log/status variants                                                                                                                                                                       | Weak / rewrite                        | `TestGitCommands::test_status_and_log_filter_unrelated_files` creates an unrelated file and commit, then checks exclusion. Keep distinct no-project, no-changes and no-remote cases.                                                                                                        |
| `unit/test_map_errors.py` directory-to-manifest resolution assertion                                                                                                                                                               | Weak / rewrite                        | Assert successful resolution and expected fields; previously it only excluded one particular error message. Retain other usage-error cases.                                                                                                                                                 |
| `commands/test_status_validation.py` detailed status disjunction                                                                                                                                                                   | Weak / rewrite                        | Require both the detailed annotation section and creator content. Either alone was insufficient evidence.                                                                                                                                                                                   |
| `unit/test_wizard_axis_edit.py` ten diff/rewrite fragments                                                                                                                                                                         | Too granular / merge                  | Three `test_scan_edit_*` tests exercise complete rename, axis removal and unchanged-name edits while checking retained bindings. Keep `test_rewrite_selector_atomic_swap`: this lower-level case remains distinct because preserving existing axis names is deliberate at the editor level. |
| `unit/test_wizard_intent_sync.py::test_sync_drops_relation_when_intent_drops_it`                                                                                                                                                   | Redundant / delete                    | Covered by `test_sync_drops_relation_whose_intent_is_gone_regardless_of_entities`; keep entity-removal cleanup and preservation of unrelated endpoints.                                                                                                                                     |

Paths in the table are under `tests/`. The [complete ID ledger](evidence/test-decisions.json)
contains exact retained, retired and added IDs for every file, including unchanged
cases. The [assertion/fixture inventory](evidence/test-inventory.txt) supports the
review; it is a baseline snapshot, not another test suite.

## Protection and support cleanup

New integration tests cover full single-file assembly, duplicate sheet names,
compression, nested Parquet/JSON, HDF5, SOFT, images, unsupported archives,
malformed input, unnamed fields, declared numeric property types and an offline
CLI/wizard workflow. Invalid named selectors, cycles and unfinished bindings must
fail visibly. A timestamp test checks single-file drift without scanning unrelated
project files.

Replacement checks passed before predecessor deletion: [101 focused cases](evidence/audit-replacement-checks.txt).
The first pruned suite passed [229 cases](evidence/pruned-suite.txt); two real-data
regressions were added afterward. Two startup-progress cases were then added
for Vlad's manual feedback; they verify that both ingestion paths show progress
before importing baker and initializing handlers ([red](evidence/startup-progress-red.txt),
[green](evidence/startup-progress-green.txt)). Product changes followed the red/green evidence
linked from the spec. Two replacement-test assumptions were corrected before
pruning: Git's parsing of a far-future date, and the editor's intentional
preservation of unchanged axis names. Neither justified a product change.

Removed the unused registry/MCP fixtures, two source-data fixtures that only
served retired compilation tests, and the unused FASTA sample. No snapshots or
test-only dependencies remained orphaned. DuckDB was removed because only the
deleted reader used it. Mocks remain where they isolate remote metadata validation
or interactive input; real baker and real Git calls protect the integration
boundaries. Git-availability guards remain appropriate. There are no new skips
or expected failures hiding retired functionality.

## Complete file review

Every collected file was reviewed for assertion sensitivity, retained contracts,
parameter value, mocking, setup cost, skips and downstream coupling. Unchanged
annotation, remote validation, move/remove, metadata status and workflow utility
tests retain distinct boundaries or failure paths. No deletion was justified
solely by a small test body or shared code coverage.

The counts below are collected cases, not function counts. A zero means intentional
retirement or a rename documented above.

| Reviewed file                                   | Before | After | Decision                                  |
| ----------------------------------------------- | -----: | ----: | ----------------------------------------- |
| `tests/commands/test_add.py`                    |     23 |    22 | merge, prune or strengthen / see findings |
| `tests/commands/test_annotate.py`               |     10 |     7 | merge, prune or strengthen / see findings |
| `tests/commands/test_annotate_incomplete.py`    |      4 |     4 | keep                                      |
| `tests/commands/test_annotate_staged.py`        |      3 |     2 | merge, prune or strengthen / see findings |
| `tests/commands/test_check_data.py`             |      3 |     2 | merge, prune or strengthen / see findings |
| `tests/commands/test_get.py`                    |     17 |     0 | retire / see findings                     |
| `tests/commands/test_mv.py`                     |     14 |    13 | merge, prune or strengthen / see findings |
| `tests/commands/test_remote_validation.py`      |      9 |     9 | keep                                      |
| `tests/commands/test_search.py`                 |      7 |     0 | retire / see findings                     |
| `tests/commands/test_status_mcp.py`             |      8 |     0 | retire / see findings                     |
| `tests/commands/test_status_validation.py`      |      7 |     7 | keep                                      |
| `tests/commands/test_status_workflow.py`        |      2 |     2 | keep                                      |
| `tests/commands/test_validation_patterns.py`    |     10 |     7 | merge, prune or strengthen / see findings |
| `tests/croissant/test_acquisition.py`           |      6 |     0 | retire / see findings                     |
| `tests/croissant/test_acquisition_locations.py` |      6 |     4 | merge, prune or strengthen / see findings |
| `tests/croissant/test_alignment.py`             |      5 |     3 | merge, prune or strengthen / see findings |
| `tests/croissant/test_baker_layout.py`          |      4 |     1 | merge, prune or strengthen / see findings |
| `tests/croissant/test_build_runtime.py`         |      2 |     0 | retire / see findings                     |
| `tests/croissant/test_codegen.py`               |      2 |     0 | retire / see findings                     |
| `tests/croissant/test_croissant_reader.py`      |     14 |    12 | merge, prune or strengthen / see findings |
| `tests/croissant/test_drift.py`                 |      3 |     4 | merge, prune or strengthen / see findings |
| `tests/croissant/test_inspector.py`             |      6 |     3 | merge, prune or strengthen / see findings |
| `tests/croissant/test_mapping.py`               |     34 |    21 | merge, prune or strengthen / see findings |
| `tests/croissant/test_preview.py`               |     14 |    15 | merge, prune or strengthen / see findings |
| `tests/croissant/test_registry.py`              |      1 |     0 | retire / see findings                     |
| `tests/croissant/test_scaffold.py`              |      6 |     0 | retire / see findings                     |
| `tests/croissant/test_selectors.py`             |     10 |     0 | retire / see findings                     |
| `tests/integration/test_baker_metadata.py`      |      0 |     5 | add / retained contract                   |
| `tests/integration/test_get_integration.py`     |      7 |     0 | retire / see findings                     |
| `tests/integration/test_metadata_workflow.py`   |      0 |    11 | add / retained contract                   |
| `tests/system/test_import.py`                   |      1 |     0 | retire / see findings                     |
| `tests/unit/test_biocypher_labels.py`           |      5 |     0 | retire / see findings                     |
| `tests/unit/test_build_cli.py`                  |      7 |     0 | retire / see findings                     |
| `tests/unit/test_cli.py`                        |      7 |     1 | merge, prune or strengthen / see findings |
| `tests/unit/test_git_commands.py`               |     19 |    12 | merge, prune or strengthen / see findings |
| `tests/unit/test_init.py`                       |     10 |     7 | merge, prune or strengthen / see findings |
| `tests/unit/test_map_errors.py`                 |     12 |    12 | keep                                      |
| `tests/unit/test_mapping_cli.py`                |      0 |     3 | add / retained contract                   |
| `tests/unit/test_mark_and_queue.py`             |     10 |    10 | keep                                      |
| `tests/unit/test_metadata_status.py`            |      9 |     9 | keep                                      |
| `tests/unit/test_mv_multifile.py`               |      6 |     6 | keep                                      |
| `tests/unit/test_read.py`                       |      4 |     0 | retire / see findings                     |
| `tests/unit/test_registry.py`                   |     29 |     0 | retire / see findings                     |
| `tests/unit/test_rm.py`                         |      8 |     8 | keep                                      |
| `tests/unit/test_search_ranking.py`             |      5 |     0 | retire / see findings                     |
| `tests/unit/test_utils.py`                      |      6 |     6 | keep                                      |
| `tests/unit/test_view.py`                       |      4 |     0 | retire / see findings                     |
| `tests/unit/test_wizard_axis_edit.py`           |     11 |     4 | merge, prune or strengthen / see findings |
| `tests/unit/test_wizard_intent_sync.py`         |      5 |     5 | merge, prune or strengthen / see findings |
| `tests/unit/test_wizard_status_flip.py`         |      4 |     4 | keep                                      |

## Daria feedback follow-up

The agent run exposed missing end-to-end protection despite the earlier passing
suite. Existing deferral tests now check preview and reactivation, not just model
state. Eight additional cases cover malformed YAML/endpoint errors through the
CLI and wizard, comment-preserving block/flow YAML edits, alias safety, literal
namespace agreement and its limits, and wizard deferral reporting. The complete
ledger includes these additions. No retained assertions were weakened.

[Red](evidence/daria-feedback-red.txt), [wizard red](evidence/daria-feedback-wizard-red.txt),
[52 focused checks](evidence/daria-feedback-green.txt),
[241 retained tests](evidence/retained-suite.txt). A hash-selector test needed its
required fields; the explicit-namespace test needed a copy of the frozen model.
These were test corrections, not reasons to alter product behavior.
