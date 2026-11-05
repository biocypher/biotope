# Contributing

Use [GitHub issues](https://github.com/biocypher/biotope/issues) for reproducible bugs, documentation corrections and proposed features. For a larger change, describe the problem and the behavior you intend before you start.

Read [system_docs/](system_docs/README.md) first: it describes the architecture, the decisions behind it and the development conventions, including the rules for command output.

## Development setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), clone the repository or your fork, and create a branch from `main`:

```bash
git clone https://github.com/biocypher/biotope.git
cd biotope
git switch -c docs/describe-your-change
uv sync --locked --extra dev --extra graph
```

uv installs a matching Python, and the `graph` extra brings Pyright with its own Node.js.

## Checks

```bash
uv run pyright
uv run pytest
```

GitHub runs the tests with Python 3.11 on Linux. Add focused tests for changed behavior. For a change to the skill, the CLI or the project layout, also run the end-to-end test described in [system_docs/conventions.md](system_docs/conventions.md#end-to-end-testing).

## Documentation

Documentation has three homes, one per reader: `docs/` for people who use Biotope through an agent, `skills/biotope-croissant/` for the agent that uses it, and `system_docs/` for development. Put each fact in one home and link to it from the others.

```bash
uv run mkdocs serve
uv run mkdocs build --strict
```

Keep `mkdocs.nav.yml` the same as the `nav` block in `mkdocs.yml`. Check every command and example you change.

## Pull requests and releases

A pull request explains the problem, the resulting behavior and how you checked it. Include the documentation it changes and any known limitation.

Use [Conventional Commits](https://www.conventionalcommits.org/) for commit subjects and PR titles:

- `fix: preserve annotations when refreshing source metadata`
- `feat: add a typed graph command`
- `docs: update public installation instructions`

When squash-merging, keep the final commit subject conventional; GitHub starts it from the PR title. With a merge commit, release-please reads the conventional commits in the merged history.

release-please runs after changes reach `main`. `fix` commits make a patch release and `feat` commits a minor one. `docs`, `build` and `refactor` appear in the changelog and can make a patch release. `chore` is hidden unless it marks a breaking change. Mark a breaking change with `!` and explain it in the commit body: it makes a major release. Maintainers review the release PR before publishing.

Do not edit version numbers or add a changelog entry by hand. release-please maintains `CHANGELOG.md`, the package version and the versioned lines in the files its configuration lists.
