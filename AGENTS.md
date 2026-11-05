# AGENTS.md

- **Lean implementation, maintainable architecture.** Use the simplest mechanism that works and use software architecture best practices to ensure long-term maintabability and extensibility.
- **Zero comments.** Code explains itself through names and structure: no comments, no docstrings. The one exception is a comment without which a competent maintainer would likely change the code into a bug, when no name can carry the reason, such as a workaround for a third-party bug with its issue link. The bar is very high: when in doubt, delete it.
- **Tests first.** Write tests for the desired behaviour before the code, with mocks at the boundaries, and see them fail. No phantom, trivial, redundant or over-granular tests.
- **Prose.** Plain and compact: short sentences, concrete statements, no rhetorical emphasis or repeated conclusions. Use the .agents/skills/document-tone skill.
- **Talking to the user.** Messages to user follow the .agents/skills/reporting skill.

## This project
Biotope is a framework for data representation: it turns a project's local sources, structured files and documents alike, into a graph of typed records that answers the project's questions. Some of the projects that use biotope are building the "who-does-what" knowledge graph at and institute or an ELIXIR organization, as well as agentic building of purpose-built graphs similar to opentargets (biomedical) or yago2geo (geogrpahic).

### Commands

```bash
uv sync --locked --extra dev --extra graph   # install
uv run pyright                               # type check
uv run pytest                                # unit tier
uv run mkdocs build --strict                 # docs
```