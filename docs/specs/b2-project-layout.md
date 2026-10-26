# B2: Small fixes and project layout

Needs: B1 · Roadmap decisions: 2–5 · Issues: #47, #48, #50, #57, #66

## Gap and what biotope already does

Biotope acts as if it owned the whole workspace and its git repository, keeps what people write about their data where the next bake overwrites it, and names files and tables by listing order, so new data needs hand edits. What biotope main (05aa413) does today, verified in code:

- **Terms.** croissant-baker (Baker) is the upstream tool `add` runs to describe data in Croissant JSON-LD; a bake is one such run, and a rebake (`add --rebake`) replaces a description with a fresh bake. A record set is a table in a description, and a file set is a group of files described together by a pattern. A source package, which `source generate` makes, reads one record set or one file. Revision: the fingerprint of what a source package depends on, pinned in its `schema.py` as `__source_digest__`; `graph check` reports `source.drift` when they differ. An orphaned package is one whose record set or file no longer exists under its ID. A sparse file holds only the values someone wrote.
- **Where it writes.** `init --visible` writes `project.yaml` at the project root, and `init` writes a `.gitignore` that ignores `/data/` when the project has none (`biotope/commands/init.py:151-153`). `extract run` writes records to a top-level `extracted/`, and the docs and skill put schemas in a top-level `extraction/` (#66). The scaffold's `graph/.gitignore` does not ignore the `graph/metagraph.html` that `graph metagraph` writes.
- **Git.** `init` runs `git init` and commits with no pathspec, so it commits whatever the user had staged, and in a subfolder of a repository it creates a nested one (`init.py:155-187`). `add`, `annotate`, `extract`, `mv`, `rm` and `source` stage `.biotope/`; `add` fills the creator from the git user; `mv` refuses to run without git (`biotope/commands/mv.py:78`) and leaves a records file's extraction state behind, so the next run calls the model for every document again; `status` reads `git status` and `git diff --cached`; `commit`, `log`, `push` and `pull` wrap git. Only `extract run` warns when git ignores a file it writes (#57).
- **Annotations.** The `.biotope.yaml` template that `add DIR` writes exists only for folders, has no column level, sits in the data folder where git usually ignores it, and is rewritten on every bake; `add` flags such as `--description` are reverted by `--rebake`. `annotate apply` merges only non-empty values, so a blank cannot clear one; it adds a `biotope` namespace to `@context` and marks the dataset curated. A curated dataset refuses a rebake, to protect registered corrections (`biotope/graph/sources.py:291-298`), so refreshing it takes `add --bake-to`, a hand reconciliation and `source register --replace` (`docs/mapping.md:65-75`), and registering a fresh bake silently restores a creator or licence that curation removed. The skill tells agents to edit a JSON-LD copy and register it. Annotating an extracted dataset makes the next `extract run` fail.
- **Source revisions.** A record set's revision digests the `@context` and that record set, table and column descriptions and file `@id`s included (`biotope/graph/sources.py:429-431`), so a description change, or the namespace `annotate` adds, fails `graph check` with `source.drift` until `__source_digest__` is edited by hand. A file's package includes the file's checksum in its revision (`sources.py:434-436`), so a changed document fails too.
- **File and table IDs.** Baker 0.6.0 numbers files in filesystem listing order (`Path.rglob`), so a new file can renumber the others and the same data gets other IDs on another machine. `graph check` then fails with `source.drift`, and updating only `__source_digest__` lets the build pass while loaders read the wrong files; the skill's example hard-codes `file_0`. A file Baker cannot parse gets `file_<sha256[:8]>` (`biotope/metadata.py:399`), so a re-downloaded document gets a new ID when its bytes changed and orphans its package, and two files can share an ID (#47). Table IDs come from file basenames, prefixed with folders on a clash, so a same-named file in another folder renames tables.
- **Topology.** `graph scaffold` creates only `topology/__init__.py`, the skill's worked example puts a node and its edge in `__init__.py`, and `graph check` only requires classes to sit inside `code_paths`.
- **Open issues.** Baker writes `contentUrl` relative to the folder it scanned, and biotope compares it with project-relative paths, so `mv` and `rm` refuse files Baker described (#48, `biotope/metadata.py:280-284`). Baker links `table.csv.gz` to `table.csv` with `sameAs`, which biotope reads nowhere, so the `.gz` becomes a duplicate source. `Pipeline.dependencies` only adds names to the versions `run.json` records (`biotope/graph/build.py:114`); nothing sets it. Reserved property names such as `preferred_id` are caught only at export (#50).

## Goal and why

After B2, biotope is one part of a project, not the whole project. Vlad: "Biotope is only part of the project, not the whole project, so it shouldn't pollute the workspace"; "`.biotope` is like .git or .dvc — just some meta and technical data"; "graph/ is an actual data product we build"; "writing to data/ for extracted records is correct". Biotope writes only in its own places, never writes to git, keeps extraction and topology in a clear layout, gives people one annotation file per dataset that it never overwrites, and keeps file and table IDs stable, so new data of the same shape rebuilds with commands only. A project such as REACH keeps its biotope project inside its own repository, and B4 rebuilds REACH after new data without a hand edit. Biotope has no users yet, so breaking changes are fine and need no migration code.

The milestone respects these decisions of #53:

- Decision 2: "Stable IDs follow common industry practice. Every build is a full rebuild." A project's key map "stays project code until a second project needs the same thing" (B3).
- Decision 3: "Public documents only go to external models in this version: public web pages, public ERC calls and InTRAC's published papers."
- Decision 4: "Testing and development use only `deepseek/deepseek-v4.1-flash` through OpenRouter. The bar is reasonable results and an end-to-end run, not full accuracy."
- Decision 5: "Git belongs to the project, not to biotope. Biotope does not presume or require git, and it never writes to git: no `git init`, no staging, no commits, and `biotope commit`, `log`, `push` and `pull` are retired. When a repository exists, biotope may read it, for example to warn that git ignores a file biotope needs committed."

## Scope

- Biotope writes only in its own places and never to git, and warns when git ignores a file it needs committed (#57).
- The extraction layout (#66) and the topology layout.
- One annotation file per dataset.
- Stable file and table IDs (#47), #48 and the three decisions of #50.
- The docs these changes need, and the new rule for specs.

## Non-goals

- REACH's own key map (B3), and REACH on biotope with output that matches its current release (B4).
- Following data into a new folder per download, such as a run ID. Such a folder enters every ID unless it sits above the dataset root, so the project shows biotope a fixed path; that is the project's to solve (B4).
- A layout for mappings, or any check of it. Topology layout checks beyond `graph check`.
- Tracking the identical copies `add` skips (#50).
- Proposing an ID mode upstream in croissant-baker.
- #26, #17, #12 and #8 (one git module, no longer needed); the ELIXIR Atlas, testing AI maintenance without a human, and internal documents.

## Interfaces

**Biotope's places.** A biotope project sits at the host repository's root, such as `.biotope/` and `graph/` beside the project's `src/`. Inside the project, biotope writes only in these, and in the files the user names to `mv`, `rm` or `--out`:

- `.biotope/`: metadata and technical state, such as the configuration, `project.yaml` (always here: `init --visible` is retired), the Croissant descriptions in `.biotope/datasets/`, the contracts and the extraction state.
- `graph/`: the graph workspace, the project's code and the data product it builds. The `graph/.gitignore` that `graph scaffold` writes ignores `graph/build/` and `graph/metagraph.html`.
- `data/`, by convention the project's data folder: extracted records default to `data/extracted/<schema>.jsonl` and stay committed. `--out` can name another path, and nothing enforces the folder name.
- Annotation files, next to each dataset the user adds, wherever the user keeps it (`add DIR` takes any folder).
- The root `.gitignore`, which `init` writes only when the project has none; an existing one is never touched. The new `.gitignore` holds `/data/**`, `!/data/**/`, `!/data/**/*.biotope.yaml` and `!/data/extracted/**`, so data files stay ignored while annotation files and records are committed, plus today's `__pycache__/`, `*.pyc` and `.venv/`. A project with its own `.gitignore` replaces a `/data/` rule with `/data/**` and adds the same exceptions.

**Git.** No command runs a git operation that writes. `commit`, `log`, `push` and `pull` are retired. `mv` works without git. `status` stops reading git: it lists the manifests and those that changed since their source package was generated; checksums stay with `check-data`; `--porcelain` and `--biotope-only` are retired. Every command that writes a file biotope needs committed (manifests, contracts, records, annotation files) warns, changing nothing, when the project's git ignores it. `init --no-git` is retired, a consequence of decision 5, since `init` never runs git. Biotope writes no creator or licence nobody gave, neither from the environment (the git user) nor from a tool's default (croissant-baker's CC BY 4.0). Generated descriptions and dates stay as they are.

**Extraction layout.** Extraction schemas live in `graph/extraction/<kind>.py` and are part of the pipeline's tracked code (`code_paths`), so `graph check` type-checks them and `run.json` records them. `biotope mv` moves a records file's extraction state (`.biotope/extraction/<path>.json`) with it.

**Topology layout.** `graph/topology/<node>/node.py` holds the node class, and the folder holds one file per edge whose source is that node, such as `sample/from_person.py`. `graph check` fails when a node or edge class sits in the wrong file. Other modules, such as helpers and shared types, are free. Mappings stay as they are in `graph/mappings/<concept>/`, unchecked.

**Annotation file.** One sparse annotation file per dataset is the single home for everything people and agents write about it: a missing value is taken from the data, and an empty value clears it. It lives next to the data, as the template does today: `<dataset folder>/.biotope.yaml` (Vlad: "next to the data it is"). It exists from the first `biotope add`, before any graph workspace. For a dataset added as a single file, it sits beside that file under a name that ends in `.biotope.yaml`.

- It holds dataset fields (name, description, licence, creator, citation and the like), file set names, table and column descriptions, keys and equivalent properties. Column types and nullability stay in each source's `schema.py`. Commands that annotate write into this file only values the user gives, never values inferred from the data, and keep its comments.
- The Croissant description in `.biotope/datasets/` is regenerated from the data plus the annotation file and is never edited by hand. Every command that reads a dataset's description uses the annotation file's current content, so a hand edit takes effect with no other step; how is the implementer's.
- The file replaces the `.biotope.yaml` template and the skill's path of copying the JSON-LD, editing it and registering it. A rebake always succeeds and re-applies the annotation file: the refusal to rebake a curated dataset, `add --bake-to` and the path that registers a hand-edited description (`source register --replace`) are retired.
- An extracted dataset's field descriptions come from its extraction schema. Its annotation file may add dataset-level fields, and `extract run` never fails because a dataset is annotated.
- A source's revision covers structure only, meaning what a source package's code depends on: fields, column types, nullability, keys and file references. Descriptions and equivalent properties do not fail `graph check`. The implementer decides by this definition which other Croissant properties count.

**File and table IDs.** File and table IDs do not change when other files are added, when a file's content changes, or on another machine. The rule below follows common practice: the path as identity in RO-Crate, OpenLineage and DVC; a declared name in Frictionless, dbt, Kedro and Hugging Face. An ID depends only on the item's own path relative to the dataset root, never on listing order, other files, content or the machine.

- A file's ID is that path in POSIX form, such as `push/records.jsonl`, in Unicode NFC with unsafe IRI characters percent-encoded, never shortened.
- A table's ID is its file's ID, `#` and the table's name inside the file: a sheet, an HDF5 dataset, a FHIR resource type, or the file stem for a single-table file, such as `push/records.jsonl#records`. A table read from a file set has the ID `<file set name>#<table>`. A field's ID stays `<table>/<column>`. A file set is named by whoever creates it, a Baker handler or the user, never by position.
- Collisions: paths that differ only in case are rejected, and a file set name used twice fails until the user renames one. No ID gets a suffix that depends on order or on other files.
- Content hashes stay checksums and the test for identical copies (`sameAs`), never IDs. #47 is resolved by it, because content hashes are no longer IDs.
- `biotope mv` updates in one step the moved file's ID, every reference to it in the description, and the source packages' declarations and file references, `__source_digest__` included, since a move changes no meaning. After the same move made outside biotope and the documented refresh, `graph check` fails, naming the old and the new ID.
- A change of a file's content alone makes no source package stale: checksums are not part of a revision, and `check-data` reports the change.

**Other contracts.** Files croissant-baker described count as tracked by every command, `mv` and `rm` included (#48). `source generate` makes no separate source from a file entry that has `sameAs` (#50). `Pipeline.dependencies` is retired: `graph/pyproject.toml` is the one declaration, and `run.json` records the versions of everything declared there plus everything the graph code imports (#50). `graph check` reports a topology property whose name the export reserves, such as `preferred_id`, before any build (#50).

## Acceptance criteria

Unit tests run on small public fixtures, with a fake OpenAI-compatible endpoint for extraction.

- **AC-1** (unit) In a temporary host repository that already holds its own code, a `.gitignore`, a `data/` folder, and staged and unstaged changes, the test runs `init`, `add`, `annotate`, `source generate`, `graph scaffold`, `graph check`, `graph build`, `graph metagraph`, `extract run`, `mv` and `rm` in turn. After each, every file created, changed or deleted lies under `.biotope/`, `graph/` or `data/extracted/` or is an annotation file, apart from the files the user named to `mv` or `rm`. The `.gitignore` is unchanged, git ignores `graph/build/` and `graph/metagraph.html`, and the repository's commits, branches and staged content are unchanged.
- **AC-2** (unit) `init` creates no repository, writes `project.yaml` in `.biotope/` and has no `--visible` or `--no-git`.
- **AC-3** (unit) In a fresh project with the `.gitignore` that `init` wrote, after `add` of a folder dataset nested two levels inside `data/` and of a single-file dataset, and after `extract run`, git tracks every annotation file and every records file and ignores every data file. Git also ignores `__pycache__/`, `.pyc` files and `.venv/`.
- **AC-4** (unit) With no `git` executable on the `PATH`, the commands of AC-1 and `status` succeed, `mv` included. `commit`, `log`, `push` and `pull` no longer exist. `status` lists the manifests and marks those whose revision differs from the one their source package pins, and has no `--porcelain` or `--biotope-only`.
- **AC-5** (unit) With a git user name and email configured, and no creator or licence given, no file the commands of AC-1 write holds a creator or licence: not the git user, not croissant-baker's CC BY 4.0.
- **AC-6** (unit) In a repository whose `.gitignore` ignores them, each command that writes a manifest, contract, records file or annotation file warns, naming each ignored file, and leaves the ignore rules unchanged. Without a repository, no such warning appears.
- **AC-7** (unit) With a schema in `graph/extraction/<kind>.py`, `extract run` without `--out` writes `data/extracted/<schema>.jsonl`, and with `--out` the path given. A type error in the schema fails `graph check`, and a build's `run.json` records the schema with the tracked code. After `biotope mv` moves the records file, the next `extract run` with `--out` naming the new path sends no request.
- **AC-8** (unit) `graph check` fails, naming the class, when a node class sits outside `graph/topology/<node>/node.py` or an edge class outside its own file in its source node's folder. A project that also has helper modules and shared types under `graph/topology/` passes, and so does the example project.
- **AC-9** (unit) For a folder dataset and a single-file dataset, the annotation file exists after the first `add`, before any `graph/` exists. `add` with annotation flags and the `annotate` commands write into it only the values the user gave, at dataset, table and column level, and keep a comment a person wrote there. No value inferred from the data is written into it.
- **AC-10** (unit) The Croissant description in `.biotope/datasets/` shows a value from the annotation file over the data's, takes a missing value from the data, holds the keys and equivalent properties the annotation file declares, and has no creator or licence when the file holds them empty. After a hand edit of the annotation file, `graph check` and `graph build` reflect it. After the data changes, a rebake of the annotated dataset succeeds: the annotation file is unchanged, the regenerated description still shows every annotation and every cleared value stays cleared, with no reconciliation or registration step. `add --bake-to` and `source register --replace` no longer exist.
- **AC-11** (unit) Changing only descriptions or equivalent properties in an annotation file changes no revision, and `graph check` passes. A new column, a changed column type in the data, or a changed file reference still fails it with `source.drift`.
- **AC-12** (unit) A dataset-level annotation of an extracted dataset reaches its description, its field descriptions still come from the extraction schema, and the next `extract run` succeeds and keeps the annotation.
- **AC-13** (unit) On a fixture dataset with tables, a file set and documents Baker cannot parse, including a file whose name holds a space and a decomposed accent, each file's ID is its path relative to the dataset root, in Unicode NFC with unsafe IRI characters percent-encoded; each table's ID is its file's ID, `#` and its name; and a file-set table's ID is `<file set name>#<table>`. No ID changes when the dataset root sits in another parent folder or when the files are listed in another order, as on another machine. Two paths that differ only in case, and a file set name used twice, fail with a message naming them.
- **AC-14** (unit) On a project that builds, after `biotope mv` moves a file, `graph check` passes with no hand edit and the file's source reads it at its new path. After the same move made outside biotope and the documented refresh, `graph check` fails, naming the old and the new ID. A change of a file's content alone fails neither `graph check` nor `graph build`, and `check-data` reports the changed file.
- **AC-15** (unit) On a project that builds, new data of the same shape arrives: new rows, a new file, a re-downloaded document, and a same-named file in another folder. The documented refresh, commands only, followed by `graph check` and `graph build`, passes with no hand edit; every source reads the same file as before; and every annotation survives.
- **AC-16** (unit) A file Baker described in a folder manifest counts as tracked, and `mv` and `rm` accept it (#48).
- **AC-17** (unit) For a folder holding `table.csv` and `table.csv.gz`, which Baker links with `sameAs`, `source generate` makes one source. `Pipeline` has no `dependencies`, and `run.json` records the versions of everything `graph/pyproject.toml` declares and everything the graph code imports. `graph check` reports a topology property named `preferred_id` without running a loader (#50).
- **AC-18** (manual) `docs/`, the skill, the examples and the tests name no top-level `extraction/` or `extracted/`. Vlad reads the skill, the scaffold and `docs/` and confirms: the scaffold shows the topology layout, the skill states it, and its worked example follows it; the annotation file replaces the `.biotope.yaml` template and the copy, edit and register path; and the refresh after new data is documented as commands only.
- **AC-19** (manual) `AGENTS.md` and `docs/specs/README.md` state the spec rule: newer specs supersede older ones, the current spec is the first commit of its milestone's draft PR, and a final commit deletes it before merge. `docs/specs/b1-extraction.md` is deleted.
- **AC-20** (manual) On B2's branch, before merge, an agent builds InTRAC's graph from scratch with the skill, including extraction of its published papers with `deepseek/deepseek-v4.1-flash`; no unpublished document goes to the model. The graph builds.
- **AC-21** (manual) On B2's branch, before merge, an agent builds REACH's graph with the skill from one raw download of REACH's test data, all sources, with the public CHC web pages through extraction, in a REACH worktree with REACH as the host repository. The graph builds, and biotope wrote only in its places. Matching REACH's current output is B4's bar.

## Freedom to operate

The implementer decides everything the Interfaces leave open, and documents in `docs/` what projects write or read: the annotation file's format, as long as people edit it by hand and their comments survive, and its name for a single-file dataset, as long as it ends in `.biotope.yaml`; how annotation commands and their options look; how a topology folder's name matches its node, for example how `graph check` knows `sample/` holds `Sample`, and how a file name matches its edge; how biotope detects a repository and its ignore rules; the wording of warnings and `status`; the refresh's commands; and whether a fix other than ID control lands in croissant-baker upstream, pinned to a release or commit, or in biotope.

## Design sketch (non-binding)

`extract run` already reads ignore rules with `git check-ignore` (`biotope/commands/extract.py:293`); the other commands can share that check. The annotation file can grow from today's `.biotope.yaml` scaffold, extended to single files and columns.

## Risks and open questions

- croissant-baker 0.6 to 0.8 cannot set IDs and keeps listing-order numbering on purpose (its PR #154), so biotope may have to rewrite IDs after each bake.

## Evidence required in the PR

- Unit test output and `uv run mkdocs build --strict` passing.
- Commits that break an interface are marked with `!`, so release-please makes the next minor version.
- For AC-18 and AC-19, Vlad's verdict. For AC-20 and AC-21, the agent's summary, the files biotope wrote in the host repository, the OpenRouter spend and Vlad's verdict.
- A final commit deletes this spec before merge.
