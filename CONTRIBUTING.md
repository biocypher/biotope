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
body. Maintainers review the resulting release PR before publishing.

Do not hand-edit version numbers or add a changelog entry for ordinary PRs.
Release-please maintains `CHANGELOG.md`, the package version and configured extra
files, including the root package entry in `uv.lock`.

Follow the [Code of Conduct](CODE_OF_CONDUCT.md) in project discussions and reviews.
