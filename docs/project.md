# Your project

Biotope keeps all its state in plain files in your project folder. This page says what to commit, where to write what you know about a dataset, and how to rebuild the graph when new data arrives. Run each command from the project folder.

## What Biotope writes

- `.biotope/`: the project's purpose, the creator and license that apply to every dataset, the [manifests](get-started.md#concepts), the source revisions and the extraction state. Commit it.
- `graph/`: the [graph workspace](get-started.md#concepts), with the project's code, `graph/pyproject.toml` and `graph/uv.lock`. Commit it. The build in `graph/build/` and the viewer `graph/metagraph.html` are ignored by git.
- `data/extracted/`: the records extracted from [documents](extraction.md). Commit them.
- An annotation file next to each dataset. Commit them.
- A root `.gitignore`, when the project has none.

Biotope never runs git. You commit these files with the rest of the project. When git would ignore a file that must be committed, Biotope warns you.

The `.gitignore` that Biotope writes keeps the data files under `data/` out of git, and keeps the annotation files and extracted records in:

```gitignore
/data/**
!/data/**/
!/data/**/*.biotope.yaml
!/data/extracted/**
__pycache__/
*.pyc
.venv/
.env
```

If your project already has a `.gitignore` with a `/data/` or `data/` rule, replace that rule with these four lines. Git cannot keep a file whose folder it ignores.

## The annotation file

Each dataset has one annotation file, the one place for what people and the agent know about it: `data/study/.biotope.yaml` for the folder `data/study`, and `data/raw/samples.csv.biotope.yaml` for the single file `data/raw/samples.csv`.

```yaml
description: People and reports of one synthetic study.
license: https://creativecommons.org/licenses/by/4.0/
creator: Ada Lovelace
tables:
  push/people.csv#people:
    description: One row per person.
    key: person_id
    columns:
      person_id:
        description: The person's ID in the study's export.
```

A value in the file wins over what croissant-baker reads from the data, a missing value comes from the data, and an empty value clears it. Edit the file by hand, or ask the agent. The manifest in `.biotope/datasets/` is made from the data and this file. Never edit the manifest.

## IDs come from paths

Each file's ID is its path within its dataset, such as `push/people.csv`, and each table's ID is its file's ID and its name, such as `push/people.csv#people`. New data with the same paths therefore keeps every ID, and the project's code keeps working. Keep each dataset at a fixed path. To move a file, use `biotope mv`, which updates every ID that points to it:

```bash
uv run --project graph biotope mv data/study/push/people.csv data/study/current/people.csv
```

## New data

When new data of the same shape arrives, such as new rows, a new file or a newer download of a document, rebuild with these commands:

```bash
uv run --project graph biotope add --rebake data/study
uv run --project graph biotope extract run
uv run --project graph biotope source generate .biotope/datasets/data/study.jsonld --out graph/sources
uv run --project graph biotope graph check
uv run --project graph biotope graph build
```

- Run `add --rebake` and `source generate` once per changed dataset.
- Run `extract run` when the project extracts records from documents. It extracts only the new and changed documents.

Two changes need the agent:

- **A new table or file** gets a new source package that does not read anything yet, and `graph check` fails until the agent writes it or excludes it with a reason. A project can instead exclude new inputs by default; ask the agent to set this up when the graph must rebuild unattended.
- **A change in structure**, such as a new column, a changed column type or a new key, makes `graph check` report drift. The agent reviews the change and updates the code. A changed description never causes drift.

## Check the state

- `uv run --project graph biotope status` lists the manifests and marks each one whose structure changed since its source packages were written.
- `uv run --project graph biotope check-data` compares the data files with the checksums Biotope recorded, and reports each changed file.
- The [CLI reference](cli.md) lists every command.
