# AGENTS.md

<!-- fleet:global -->

## Global rules

These rules apply in every project. Projects inherit them from `~/Projects/fleet/AGENTS.md`; change them there.

- **Lean.** Use the simplest mechanism that works. Add no layers, options or files the task does not need; harden later when a real problem shows up.
- **Zero comments.** Code explains itself through names and structure: no comments, no docstrings. The one exception is a comment without which a competent maintainer would likely change the code into a bug, when no name can carry the reason, such as a workaround for a third-party bug with its issue link. The bar is very high: when in doubt, delete it. Reasons go in commit messages.
- **Tests first.** Write tests for the desired behaviour before the code, with mocks at the boundaries, and see them fail. Test through public interfaces. No phantom, trivial, redundant or over-granular tests.
- **Prose.** Plain and compact: short sentences, concrete statements, no rhetorical emphasis or repeated conclusions.
- **Talking to Vlad.** Messages to Vlad follow `communication.md` in the `orchestrate` skill: the point first, in plain full sentences, every ID explained.
- **Repo, not memory.** Project facts, principles and decisions live in the repo, never only in an agent's memory.
- **Tags.** All agents post on GitHub through Vlad's account. Start every comment with `🤖 <family>-<role>:`, for example `🤖 claude-agent:` or `🤖 codex-review-agent:`. An untagged comment is Vlad's.

<!-- /fleet:global -->

## This project

Biotope curates Croissant descriptions of local data and builds typed, provenance-tracked BioCypher graphs from them. The current iteration makes it a reusable framework for versioned data products built from structured and unstructured local sources. REACH ([slolab/reach](https://github.com/slolab/reach)) is the testing ground and InTRAC the second user; a feature belongs in biotope only if it makes sense beyond REACH, and no spec here describes behaviour specific to one project.

Read [`docs/roadmap.md`](docs/roadmap.md) before starting any task: the terms, the settled decisions and the milestones. Live status is in issue [#53](https://github.com/biocypher/biotope/issues/53).

### Layout

- `biotope/`: the package. `commands/` holds one module per CLI command, `graph/` the typed graph engine (sources, checks, build, export), `extraction/` the extraction stage (schemas, the extractor protocol, the LLM extractor, document text and stored records), `croissant/` the Croissant models, `metadata.py` the manifest helpers (status, `prov:wasDerivedFrom`), `templates/` what `graph scaffold` and `source generate` write.
- `skills/`: the agent skills shipped in the Claude plugin (`.claude-plugin/`): `biotope-croissant` (project workflow and its ownership rules) and `biocypher`.
- `tests/`: `unit/`, `commands/`, `croissant/`, `graph/`, `extraction/` (against a fake OpenAI-compatible endpoint) and `integration/`, on fixtures in `tests/fixtures/`. `examples/` holds a typed graph example.
- `docs/`: the MkDocs site (nav in both `mkdocs.yml` and `mkdocs.nav.yml`, kept in sync), `roadmap.md`, `specs/` (one spec per milestone, format in `specs/README.md`) and `research/` (notes behind tool and model choices).

### Commands

```bash
uv sync --locked --extra dev --extra graph   # install
uv run pyright                               # type check
uv run pytest                                # unit tier
uv run pytest -m live                        # live tier, from B1: real endpoints, may cost money
uv run pre-commit run --all-files            # format and lint
uv run mkdocs build --strict                 # docs
```

### Tests, commits and releases

- Unit tests run by default and in CI, on committed public fixtures and without network. B1 adds the `live` marker for tests that call a real model endpoint, and excludes it by default with `addopts`. `manual` criteria are judged by Vlad or a project's user and recorded in the PR.
- Tests and examples use only public material (roadmap decision 14). Never commit copyrighted full text, such as the InTRAC papers; runs on such documents happen in the data projects that hold them.
- Commit subjects and PR titles follow Conventional Commits (`feat:`, `fix:`, `docs:`, …; `!` marks a break). Release-please maintains the version, `CHANGELOG.md` and `uv.lock`'s package entry: never edit them by hand.

### Secrets

- Model endpoints read keys from environment variables, such as `OPENROUTER_API_KEY`. Never read, print, log, commit or paste a `.env` file or a key, and never record one in a manifest, provenance or report.
- Work in a worktree under `/home/vladsam42/Projects/biotope_project/.worktrees/`; the main checkout is `/home/vladsam42/Projects/biotope_project/biotope`.

## Workflow

Work is planned in milestones, one spec and one PR each. The orchestrator runs it with fleet's `orchestrate` skill. Every agent follows these rules:

- Never commit to `main`. Only Vlad merges.
- A merged spec in `docs/specs/` is frozen. Never weaken, drop or reinterpret an acceptance criterion. If one is wrong or impossible, comment `BLOCKED on AC-n` with your evidence and options, and stop work on it.
- Never make a test pass by weakening it: no new skip or xfail, no removed assertions, no loosened tolerances, no mocking of the code under test.
- Generated files, such as run records and lock files, are marked `linguist-generated=true` in `.gitattributes`. Upstream code is pinned to a release or commit, never copied in.
- Out-of-scope findings become GitHub issues, not extra scope.
- End each working session on a PR with a handoff comment: done, next, blockers, open questions.
