# Conventions

## Command output

Keep command mechanics apart from structured results and their rendering. Human and JSON output use the same evidence. A renderer never reads source data and never rebuilds facts from messages.

**Human output:**

- Lead with the target and the operation, then a compact outcome.
- Group successful checks. Show every warning, error, deferral and blocked check with its subject and explanation. A problem never needs `--verbose` to appear.
- Use a fixed status column with wrapping content, as in `biotope/commands/_add_output.py`. Keep full paths and IDs, including spaces and literal markup, and align wrapped lines with their content column.
- Use little color, always with a status word. Avoid wide tables, decorative panels and lists of next steps.
- Show a spinner at once during slow work of unknown length. Keep live diagnostics above the progress line, and print them once. Disable animation when output is not a terminal and in JSON mode. Respect `NO_COLOR`.
- State the scope of the operation once: checking definitions, running without export, or running and exporting.

```text
Check     graph
OK        pipeline · topology · code · dependencies
FAIL      python
          graph/mappings/study.py:84:17
          python.argument: Expected StudyId; received GeneId.
```

**JSON output:**

- Write JSON only with an explicit `--json`, never by detecting an agent.
- Write one versioned document to stdout, also when the operation fails. Logs, dependency output and progress go to stderr.
- Keep finding codes, exact references, counts, denominators, locations and skip reasons stable and complete. Examples may be cut short when the cut is stated; distinct diagnostics are never cut.
- Exit nonzero for operational and integrity errors. Warnings alone succeed. Invalid syntax may use Click's usage errors. A missing measurement is not zero and not a passed check.

**Tests:** cover narrow terminals, long paths, literal markup, noisy imports, redirected output and a JSON failure. Check what the output contains and how it is laid out, not large snapshots. Apply these rules to new and changed commands.

## Documentation

- Write each fact in its home, as [README.md](README.md) describes: `docs/`, the skill or `system_docs/`.
- `docs/` describes only current behavior, with no history and no development notes. `CHANGELOG.md` keeps the history.
- Write prose with the document-tone skill (`.agents/skills/document-tone`). It may write secondary material to a `<name>_sidenotes.md` file during a rewrite. Delete that file before the commit.
- Keep the `nav` in `mkdocs.nav.yml` the same as in `mkdocs.yml`; the organization's documentation aggregator reads the mirror.
- The CLI reference is generated from the Click help texts, so a help text is public documentation. Write it in the same plain style.
- Run `uv run mkdocs build --strict` after every docs change.

## End-to-end testing

Unit and integration tests run with `uv run pytest`. They do not show whether an agent can build a real project with Biotope and the skill. That is tested end to end:

1. Two development datasets stand for the two kinds of project: REACH, an organization's register of who works on what, and InTRAC, a biomedical graph built from tables and published papers.
2. An agent builds each project from its raw data with the skill and the Biotope version under test, run through the agent harness [AHL](https://github.com/slolab/agent-harness-lab).
3. The run passes when the agent finishes the build, the hand-over matches the data, and a rebuild after new data needs commands only.

Run it for every change to the skill, the CLI or the project layout. Development fixtures for these runs may later live in this repository.

Two rules apply to development and testing:

- Only public documents go to external models: public web pages, public calls for proposals and published papers.
- Tests use one model, `deepseek/deepseek-v4.1-flash` through OpenRouter. The bar is a reasonable result and a complete run, not full accuracy.

## Versioning

Biotope follows [semantic versioning](https://semver.org/) from 1.0. A breaking change to the public interface comes only in a new major version. The public interface is:

- the CLI: commands, options, exit codes and the `--json` reports;
- the Python API that graph code imports: `biotope.graph` and `biotope.extraction`;
- the project files: `.biotope/`, the annotation file and the `graph/` layout rules that `graph check` enforces;
- the build outputs: `run.json`, `provenance.json` and `schema_config.yaml`.

Anything else, such as internal modules and the human-readable output, may change in any release.

Mark a breaking change with `!` in the commit subject and explain it in the body. release-please then opens a major release. release-please also updates the version in `pyproject.toml`, `uv.lock`, `.claude-plugin/plugin.json` and the versioned lines of the docs, so never edit a version by hand.
