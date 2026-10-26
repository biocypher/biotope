# B2: Releases and input checks

Needs: none · Roadmap decisions: 1, 8–14 · Research: [`docs/research/b2-b3-state.md`](../research/b2-b3-state.md), sections 1 and 2

## Goal and why

A build's run record copies the sha256 that its inputs' descriptions hold, not that of the files it read, and holds record values, so a project cannot commit it as its release history.

0.10 already has the parts. Croissant gives every described file its sha256, and `run.json` copies each source's file list with those hashes, the manifest and contract digests, the code digests and `graph_digest`. `biotope check-data` compares files with their hashes, but as a separate command: after `people.csv` is edited without being described again, `graph build` reads the new rows while `run.json` records the old hash. `run.json` also carries example property values from the quality report and absolute paths, and sits in `graph/build/`, which `graph scaffold` ignores.

After B2, a project commits each build's run record, which names the exact files the build read, and git over those records is its release history. InTRAC needs this to know which inputs produced a result. The milestone respects these roadmap decisions:

- 1 and 9 to 11: biotope stays out of identity, precedence and human decisions, which are project code.
- 8 and 12: a build is a function of its inputs and committed files; inputs are identified by their sha256; a stale description is a warning, not a stop, since sources such as REACH's are fetched again on every refresh; biotope stores no raw snapshots and no history beyond git.
- 13 and 14: the change to `run.json` gets a `migration.md` note; tests use only public material.

## Scope

- The input record: the sha256 of every file the build reads, compared with its description.
- A run record without record values or machine-specific paths, which a project made by `biotope init` and `graph scaffold` can commit.

## Non-goals

- Stopping a build on a changed input, and a refresh mechanism. A changed file is described again with the existing commands: `biotope add --force` for a file, `biotope add --rebake` for a directory, `--bake-to` with `biotope source register --replace` for a curated description, and `biotope extract run` for extracted records.
- A diff between builds. Git over the run records is the release history, and `graph_digest` says whether two builds differ. A diff by object ID is a B3 candidate if REACH pass 1 or InTRAC shows a need.
- Raw snapshots, and DVC, git-annex, lakeFS or Dolt (research note, section 2).
- Identity, precedence, ID registries and human decisions (roadmap decisions 9 to 11), topology changes (B4), and committing exports.

## Interfaces

**Input record.** For every file of every source the pipeline selects, the run record holds the sha256 of the file as the build read it. A file whose sha256 differs from its description's, or that is missing, is a warning in `graph check`, `quality` and `build` that names the file, its dataset and the command that describes it again; the build goes on. A file whose description records no sha256, such as a hand-written FileObject or a member of a FileSet, is recorded and not compared. Files of datasets that no selected source reads are neither recorded nor compared, so a clone without B1's documents still builds from their extracted records.

**Run record.** What a complete build records about itself. It holds no property values: object IDs, counts, evidence locations and the names of concepts, properties, sources and files may appear. Values that reports show today, such as quality's examples, stay in the command's output or in uncommitted build files. Its paths are relative to the project, so two clones that build the same inputs write the same run record, timestamps aside. Git tracks it and ignores the export. A failed build never writes its report where the run record is tracked.

## Acceptance criteria

Unit fixtures: two small gene tables shaped like InTRAC's studies, with public Ensembl IDs and symbols, a gene–study relation, and the records B1 extracts from its committed fixtures.

- **AC-1** (unit) After a row is added to a gene table without describing it again, `graph check`, `quality` and `build` warn, naming the file, its dataset and `biotope add --force`; the build completes and its run record holds the edited file's new sha256. After `biotope add --force`, the warning is gone. A deleted input file is warned about the same way.
- **AC-2** (unit) With B1's documents deleted, a build that selects only the extracted records completes without a warning. A source whose file has no recorded sha256, as in `examples/typed_graph`, and a source described as a FileSet complete with each file's sha256 in the run record and no mismatch warning.
- **AC-3** (unit) With a distinctive string in every property that is not an ID, the run record of a complete build, quality observations included, contains none of them, and the build's output still shows quality's examples. Building one project from two clones at different paths gives run records that differ only in timestamps.
- **AC-4** (unit) In a project made by `biotope init` and `graph scaffold`, git tracks the run record after a build and ignores the export. After one input changes, is described again and is rebuilt, the run record's git diff shows that file's new sha256 and the changed counts.
- **AC-5** (unit) In such a project, a first build that fails on a loader error whose message quotes a property value leaves nothing new for git to track.

## Freedom to operate

The implementer decides everything the Interfaces leave open and documents in `docs/` what projects read: where the run record lives and how git tracks it, where a failed build's report goes, how the warning reads, whether hashes are cached, and where values removed from the run record go.

## Design sketch (non-binding)

Reuse the comparison in `biotope/commands/check_data.py` from the sources stage of `graph/check.py`, and record its hashes where `run.json` copies each source's `distribution` today.

## Risks and open questions

- Hashing large inputs at every build may be slow; a size and modification-time cache can come later.
- Loaders are project code and open their files themselves, so biotope hashes each file when the build reaches its source, not the loader's own stream.

## Evidence required in the PR

- Unit test output, the `docs/` pages for the input record and the run record, and the `migration.md` note.
- A sample run record from the fixtures.
- `uv run mkdocs build --strict` passing.
