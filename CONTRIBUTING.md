# Contributing

Use [GitHub issues](https://github.com/biocypher/biotope/issues) for reproducible
bugs, documentation corrections and proposed features. For a larger change,
describe the problem and intended behavior before starting implementation.

## Development setup

Clone the repository or your fork, then create a branch from `main`. Install
[uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js, and use
Python 3.10–3.12:

```bash
git clone https://github.com/biocypher/biotope.git
cd biotope
git switch -c docs/describe-your-change
uv sync --locked --extra dev --extra graph
uv run python -m pyright --version
```

The lockfile resolves published dependencies, including croissant-baker. No local
sibling package is required. If Node.js is unavailable, install `pyright[nodejs]`
in the environment as described in the [installation guide](docs/installation.md).

## Checks

Run the checks relevant to your change:

```bash
uv run pyright
uv run pytest
uv run pre-commit run --all-files
```

Pre-commit manages formatting, linting and configuration checks in its own
environments. Its first run downloads those tools. The GitHub test matrix covers
Python 3.10 and 3.12 on Linux and macOS.

Add focused tests for changed behavior. For documentation-only changes, verify the
commands and examples you alter and build the documentation.

## Command output

Keep command mechanics separate from structured results and their presentation.
Use the same evidence for human and JSON output; renderers must not read source
payloads or reconstruct facts from messages.

**Human output.** Lead with the target and operation, then a compact outcome.
Group successful checks. Show every actionable warning, error, deferral and
blocked check with its subject and explanation. Do not require `--verbose` to
discover problems.

Use a fixed status column and wrapping content, as in
`biotope/commands/_add_output.py`. Preserve full paths and identifiers, including
spaces and literal markup. Align wrapped lines with their content column. Use
restrained colour plus explicit status words; avoid wide tables, decorative
panels and repetitive next-step lists.

```text
Check  graph/
OK     Sources · topology · requirements
FAIL   Python
       graph/mappings/study.py:84:17
       Expected StudyId; received GeneId.
```

Show a spinner immediately during slow work when totals are unknown. Keep live
diagnostics above progress, and avoid printing them twice. Disable animation on
non-terminal output and in JSON mode. Respect `NO_COLOR`. State the operation's
scope once: definition checking, execution without export, or execution/export.

**JSON output.** Use explicit `--json`, not agent detection. Write one versioned
document to stdout, including operational failures. Keep logs, incidental
dependency output and progress on stderr. Preserve stable finding codes, exact
references, counts, denominators, locations and skipped reasons. Examples may be
bounded, with truncation explicit; distinct diagnostics must remain complete.

Do not infer JSON from rendered text. Exit nonzero for operational/integrity
errors; advisory warnings alone succeed. Invalid command syntax may use Click's
ordinary usage errors. Missing measurements are not zero or successful checks.

**Verification and scope.** Test meaningful output scenarios: narrow terminals,
long paths, literal markup, noisy imports, redirected output and a JSON failure.
Check information and layout invariants instead of maintaining large snapshots or
trivial cases. Apply these standards to new and changed commands; do not rewrite
unrelated commands to satisfy them.

References: [uv output controls](https://docs.astral.sh/uv/reference/cli/),
[pnpm reporters](https://pnpm.io/cli/install#--reportername),
[Homebrew colour controls](https://docs.brew.sh/Manpage).

## Documentation

```bash
uv run mkdocs serve
uv run mkdocs build --strict
```

Keep `mkdocs.nav.yml` synchronized with the `nav` block in `mkdocs.yml`. Write
examples for a public installation unless the page explicitly covers development.
Keep a guide's main workflow short; link detailed contracts or secondary examples
from a companion notes page.

## Pull requests and releases

A pull request should explain the problem, resulting behavior and validation.
Include relevant documentation updates and identify any known limitation.

Use [Conventional Commits](https://www.conventionalcommits.org/) for commit subjects
and PR titles. Examples:

- `fix: preserve annotations when refreshing source metadata`
- `feat: add a typed graph command`
- `docs: update public installation instructions`

When squash-merging, keep the final commit subject conventional; GitHub usually
starts it from the PR title. With a merge commit, release-please can inspect the
conventional commits in the merged history. A PR title alone does not rewrite them.

The release-please workflow runs after changes reach `main`. `fix` and `feat`
commits contribute patch and minor changes respectively. This repository also
includes `docs`, `build` and `refactor` in visible changelog sections, so those
changes can produce a patch release. `chore` is hidden unless it marks a breaking
change. Mark a breaking change with `!` and explain it in the commit
body; before 1.0, a breaking change raises the minor version. Maintainers review
the resulting release PR before publishing.

Do not hand-edit version numbers or add a changelog entry for ordinary PRs.
Release-please maintains `CHANGELOG.md`, the package version and configured extra
files, including the root package entry in `uv.lock`.

Follow the [Code of Conduct](CODE_OF_CONDUCT.md) in project discussions and reviews.
