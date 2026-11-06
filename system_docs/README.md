# System docs

This folder is for agents and people who develop Biotope. It records how Biotope is built, why, and the rules for changing it. It is read in the repository and is not part of the published site.

## Three homes

Biotope's documentation has three homes, one per reader. Each fact has one home: the reader who acts on it in the most detail owns it, and the other homes link to it.

| Home | Reader | Holds |
| --- | --- | --- |
| `docs/` (the public site) | A person who uses Biotope through a coding agent | What Biotope does, how to start, what the person decides, how to use and keep the result |
| `skills/biotope-croissant/` | The agent that uses Biotope in a project | How to use Biotope to build and maintain a knowledge representation |
| `system_docs/` | An agent or person that develops Biotope | The architecture, product decisions with their reasons, development conventions |

Working specs and notes for one piece of work go to the gitignored `spec_files/`.

## Read first

1. [architecture.md](architecture.md): the modules, the data flow, the execution boundaries and the invariants.
2. [decisions.md](decisions.md): what Biotope does and leaves to the project, and why.
3. [conventions.md](conventions.md): command output, documentation, end-to-end testing and the versioning promise.
