# AGENTS.md
- **Lean implementation, maintainable architecture.** Use the simplest mechanism that works and use software architecture best practices to ensure long-term maintabability and extensibility.
- **Zero comments.** Code explains itself through names and structure: no comments, no docstrings. The one exception is a comment without which a competent maintainer would likely change the code into a bug, when no name can carry the reason, such as a workaround for a third-party bug with its issue link. The bar is very high: when in doubt, delete it.
- **Tests before feature, not after.** If you are developing or updating a feature, write tests for the desired behaviour before the code, with mocks at the boundaries. No phantom, trivial, redundant or over-granular tests. Not everything has to be tested. When something is removed, remove corresponding tests.
- **Prose.** Plain and compact: short sentences, concrete statements, no rhetorical emphasis or repeated conclusions. Use the .agents/skills/document-tone skill.
- **Talking to the user.** Messages to user follow the .agents/skills/reporting skill.

## This project
Biotope is a framework for data representation: it turns a project's local sources, structured files and documents alike, into a graph of typed records that answers the project's questions. Some of the projects that use biotope are building the "who-does-what" knowledge graph at and institute or an ELIXIR organization, as well as agentic building of purpose-built graphs similar to opentargets (biomedical) or yago2geo (geographic).

Conceptually, we are not building only the biotope codebase, or only the agent skill. Biotope is a package as a whole: a framework operated by an agent. We are responsible both for the biotope and the agent's behaviour.

Biotope agent builds a knowledge representation using a biotope framework with a human in the loop. We are responsible for the agent and the framwork to impose best practices and make building and maintaining the data project as easy as possible, but semantic authority for the purpose and final decisions on the representation stays with the human.

## Documentation structure
- `docs/`: the public site, for people who use Biotope through an agent. No development leftovers or _sidenotes files.
- `skills/biotope-croissant/`: for the agent that uses Biotope in a project to build and maintain a knowledge representation.
- `system_docs/`: for agents that develop Biotope: architecture, invariants, decisions and conventions.
- Working documents and specs go into the gitignored `spec_files/`.

### Commands

```bash
uv sync --locked --extra dev --extra graph   # install
uv run pyright                               # type check
uv run pytest                                # unit tier
uv run mkdocs build --strict                 # docs
```