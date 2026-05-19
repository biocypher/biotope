# `biotope chat`

Provider-agnostic conversational interface to a project's KG. v1 ships the biochatter backend behind a `--backend` slot so additional backends (local LLMs, Claude Code sessions) can land without reshaping the command.

Biochatter is not declared as a dependency because of a transitive `pillow` conflict with `croissant-baker`. Install explicitly when needed: `uv pip install biochatter`.

::: biotope.commands.chat
