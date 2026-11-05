# System docs

This folder is for agents and people who develop Biotope. It records how Biotope is built, why, and the rules for changing it. It is read in the repository and is not part of the published site.

## Three homes

Biotope's documentation has three homes, one per reader. Each fact has one home: the reader who acts on it in the most detail owns it, and the other homes link to it.

| Home | Reader | Holds |
| --- | --- | --- |
| `docs/` (the public site) | A person who uses Biotope through a coding agent | What Biotope does, how to start, what the person decides, how to use and keep the result, the CLI reference |
| `skills/biotope-croissant/` | The agent that uses Biotope in a project | The workflow, the contracts it codes against, finding codes and their fixes, the edge cases it acts on |
| `system_docs/` | An agent or person that develops Biotope | The architecture, the invariants tests guard, product decisions with their reasons, development conventions |

For example, "keep each dataset at a fixed path" is in `docs/`. The skill says how to resolve a package orphaned by a move. [architecture.md](architecture.md) states the invariant behind both: an ID depends only on the path.

Working specs and notes for one piece of work go to the gitignored `spec_files/`.

## Read first

1. [architecture.md](architecture.md): the modules, the data flow, the execution boundaries and the invariants.
2. [decisions.md](decisions.md): what Biotope does and leaves to the project, and why.
3. [conventions.md](conventions.md): command output, documentation, end-to-end testing and the versioning promise.

The project rules for code and prose are in [AGENTS.md](../AGENTS.md). Plans and status are in issue [#53](https://github.com/biocypher/biotope/issues/53).
