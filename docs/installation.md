# Installation

Biotope 0.9 supports Python **3.10–3.12**. The `graph` extra installs BioCypher
and Pyright for typed graph checking and export. The base package supports the
metadata workflow without those graph dependencies.

## Install the published package

The examples below use [uv](https://docs.astral.sh/uv/getting-started/installation/)
and a POSIX shell on Linux or macOS:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python 'biotope[graph]>=0.9,<0.10'
source .venv/bin/activate
biotope --version
```

croissant-baker is installed from PyPI as a dependency. A sibling checkout or
editable croissant-baker installation is unnecessary.

Pyright needs [Node.js](https://nodejs.org/en/download) on `PATH`. To let the
Pyright package supply its runtime instead:

```bash
uv pip install --python .venv/bin/python 'pyright[nodejs]'
python -m pyright --version
```

The first invocation may download Node.js. Prepare this runtime before using an
environment without network access.

### Existing uv project

Add Biotope to the project's dependencies and run commands through its environment:

```bash
uv add 'biotope[graph]>=0.9,<0.10'
uv run biotope --version
```

The same Node.js requirement applies. Record any libraries needed by your own
loaders in the project's dependencies too.

### Standard Python environment

With Python 3.10–3.12 selected:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install 'biotope[graph]>=0.9,<0.10'
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell and use
`.venv\Scripts\python.exe` where these examples use `.venv/bin/python`.

For metadata-only work, install `biotope` in place of `biotope[graph]`.
A one-off scaffold can also be created with `uvx biotope init my-kg`; subsequent
graph work needs a project environment with the `graph` extra.

## Create a project

```bash
biotope init my-kg
cd my-kg
biotope graph scaffold
```

`init` creates metadata configuration and purpose files. `graph scaffold` adds
the Python graph workspace, including a dependency declaration in `graph/`.
Neither command installs dependencies or completes a pipeline. Adapt the scaffold
using the [typed graph guide](mapping.md), or run the completed [tutorial](tutorial.md).

## Develop Biotope itself

From a repository checkout:

```bash
uv sync --locked --extra dev --extra graph
uv run python -m pyright --version
uv run pytest
```

This uses the published croissant-baker version in `uv.lock`. See
[the contributor guide](https://github.com/biocypher/biotope/blob/main/CONTRIBUTING.md)
for the full checks and documentation build.
