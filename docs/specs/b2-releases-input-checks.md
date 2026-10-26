# B2: Releases and input checks

Needs: none · Roadmap decisions: 1, 8–14 · Research: [`docs/research/b2-b3-state.md`](../research/b2-b3-state.md), sections 1 and 2

## Goal and why

A build never checks its input files against the sha256 it records, its run record holds record values so a project cannot commit it, and nothing says what changed between two builds.

0.10 already has the parts. Croissant gives every described file its sha256, and `run.json` copies each source's file list with those hashes, the manifest and contract digests, the code digests and `graph_digest`. `biotope check-data` compares files with their hashes. `graph build --out` writes a build to any directory. They are not joined up: `check-data` is a separate command, so after `people.csv` is edited without being described again, `graph build` reads the new rows while `run.json` records the old hash. `run.json` also carries example property values from the quality report and absolute paths, and sits in `graph/build/`, which `graph scaffold` ignores. `graph_digest` tells whether two builds differ, not what differs.

After B2, a build reads only the files its descriptions name, a project commits each build's run record and has its release history in git, and a person or agent sees which objects a rebuild added, removed or changed. REACH needs this to show Anna what a rebuild changed; InTRAC to know which inputs produced a result. The milestone respects these roadmap decisions:

- 1 and 9 to 11: biotope stays out of identity, precedence and human decisions, which are project code.
- 8 and 12: a build is a function of its inputs and committed files; inputs are identified by Croissant's sha256; biotope stores no raw snapshots and no history beyond git.
- 13 and 14: a build that now refuses a changed input is a break with a `migration.md` note; tests use only public material.

## Scope

- The input check, run by `graph check`, `quality` and `build`.
- A run record without record values or machine-specific paths, which a project made by `biotope init` and `graph scaffold` can commit.
- A diff between two complete builds by object ID.

## Non-goals

- A refresh mechanism. A changed file is described again with the existing commands: `biotope add --rebake`, `--bake-to` with `biotope source register --replace` for a curated description, and `biotope extract run` for extracted records.
- Raw snapshots, and DVC, git-annex, lakeFS or Dolt (research note, section 2). A release history other than git over the run records.
- Recording hashes that a description lacks, such as those of FileSet members.
- Identity, precedence, ID registries and human decisions (roadmap decisions 9 to 11), and topology changes (B4).
- Committing exports; diffing run records, which git does.

## Interfaces

**Input check.** For every source the pipeline selects, biotope compares each file its description lists with the recorded sha256, as `check-data` does, before any loader runs. A file that differs or is missing stops `quality` and `build`, which keep the previous build, and names the file, its dataset and the command that describes it again; `graph check` reports the same finding. Files of datasets that no selected source reads are not checked, so a clone without B1's documents still builds from their extracted records. A file whose description records no sha256, such as a hand-written FileObject or the members of a FileSet, is reported as unchecked and does not stop the build.

**Run record.** What a complete build records about itself. It holds no property values: object IDs, counts, evidence locations and the names of concepts, properties, sources and files may appear. Values that reports show today, such as quality's examples, stay in the command's output or in uncommitted build files. Its paths are relative to the project, so two clones that build the same inputs write the same run record, timestamps aside. Git tracks it and ignores the export.

**Diff.** Between two complete builds of a project: per concept, the IDs of objects added and removed, and for each object present in both with different property values, the names of those properties. Edges are matched by the identity the runtime gives them, their `id` or their type and endpoints. `biotope_provenance_id` is local to a build and is not compared. The output is readable by a person and available as structured output, like the other `graph` commands.

## Acceptance criteria

Unit fixtures: two small gene tables shaped like InTRAC's studies, with public Ensembl IDs and symbols, a gene–study relation, and the records B1 extracts from its committed fixtures.

- **AC-1** (unit) After a row is added to a gene table without describing it again, `graph build` writes no new build, keeps the previous one, and names the file, its dataset and the command to describe it again; `graph check` and `quality` report the same. After the file is described again with that command, the build runs. A deleted input file is reported the same way.
- **AC-2** (unit) With B1's documents deleted, a build that selects only the extracted records runs. A source whose file has no recorded sha256, as in `examples/typed_graph`, and a source described as a FileSet are reported as unchecked, and the build completes.
- **AC-3** (unit) With a distinctive string in every property that is not an ID, the run record of a complete build, quality observations included, contains none of them, and the build's output still shows quality's examples. Building one project from two clones at different paths gives run records that differ only in timestamps.
- **AC-4** (unit) In a project made by `biotope init` and `graph scaffold`, git tracks the run record after a build and ignores the export. After one input changes, is described again and is rebuilt, the run record's git diff shows that file's new sha256 and the changed counts.
- **AC-5** (unit) Between two builds of the gene fixtures in which one gene was added, one removed, one symbol changed and one relation's property changed, the diff lists exactly that gene as added, that gene as removed, the symbol for the changed gene and the property for the changed relation. Two builds of unchanged inputs, with the sources and their records shuffled, give an empty diff.

## Freedom to operate

The implementer decides everything the Interfaces leave open and documents in `docs/` what projects read: where the run record lives and how git tracks it, how the input check reports and caches, where values removed from the run record go, whether the diff reads the export files or a listing the build writes, and the diff command's name, options and output format.

## Design sketch (non-binding)

Call the comparison in `biotope/commands/check_data.py` from the sources stage of `graph/check.py`. The diff is a join on ID per concept, a few dozen lines with no dependency (research note, section 2). `graph build --out` already puts two builds side by side.

## Risks and open questions

- Hashing large inputs at every check may be slow; a size and modification-time cache can come later.
- A curated source that changes on every fetch, such as REACH's exports, needs `--bake-to` and `source register --replace` each time. If REACH pass 1 finds that too heavy, it is a B3 candidate.
- InTRAC's full build has about 1.3 million nodes and 3.5 million edges, so the diff must not hold two builds' values in memory several times over.

## Evidence required in the PR

- Unit test output, the `docs/` pages for the input check, the run record and the diff, and the `migration.md` note.
- A sample run record and diff from the fixtures.
- The diff's time and peak memory on a generated project of InTRAC's size.
- `uv run mkdocs build --strict` passing.
