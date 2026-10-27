# Commands

Run project commands from the project root with its environment activated. Use
`biotope <command> --help` for options. With a uv-managed environment, prefix
commands with `uv run`. [Project layout](project.md) describes where each command
writes and what the project commits.

## Initialize and describe

| Command                          | Purpose                                                                       |
| -------------------------------- | ----------------------------------------------------------------------------- |
| `biotope init my-kg`             | Create a project in a new subdirectory.                                       |
| `biotope init . --no-prompt`     | Initialize the current directory, such as a repository's root, with defaults. |
| `biotope add <path>...`          | Describe local files or directories with croissant-baker.                     |
| `biotope add <path> --json`      | Emit per-file scan outcomes and diagnostics as JSON.                          |
| `biotope map inspect <manifest>` | Inspect record sets and declared field types without reading payloads.        |

`init` writes `.biotope/config.yaml` and `.biotope/project.yaml`, and a root
`.gitignore` only when the project has none. It runs no git command and creates
no graph workspace. Baking and checksum verification read source bytes; metadata
inspection does not.

`add` writes the description to `.biotope/datasets/` and creates the dataset's
annotation file next to the data. `add --rebake <path>` describes an added dataset
again from its data and applies its annotation file again; it always succeeds.
`--force` does the same.

## Annotate

```bash
biotope annotate set data/study description="People of one study."
biotope annotate set data/study --table 'push/people.csv#people' key=person_id
biotope annotate set data/study --table 'push/people.csv#people' --column name description="Full name."
```

`annotate set` writes the values given into the dataset's
[annotation file](project.md#the-annotation-file): the dataset's without
`--table`, a table's with `--table <ID>`, and a column's with `--column <name>`. A
repeated key makes a list and an empty value clears. The `add` flags such as
`--description`, `--license` and `--creator` write dataset fields into the same
file. `annotate validate --jsonld <file>` runs the external `mlcroissant`
validator on a description.

## Extract records from documents

| Command                                               | Purpose                                                                       |
| ----------------------------------------------------- | ----------------------------------------------------------------------------- |
| `biotope extract try <module.py:Schema> <file>...`    | Show the records and evidence the configured extractor finds; change nothing. |
| `biotope extract run <module.py:Schema> <dataset>...` | Extract registered documents, store the records and register them.            |
| `biotope extract text <file>`                         | Print biotope's text of a document, which evidence offsets refer to.          |
| `biotope extract schema <module.py:Schema>`           | Print the JSON Schema, key and revision biotope derives from a schema class.  |

Extraction reads the extractor from `extraction` in `.biotope/config.yaml` and
reuses stored records until a document, the schema or the extractor changes.
Schemas live in `graph/extraction/<kind>.py`, and records go to
`data/extracted/<schema>.jsonl` unless `--out` names another file. See
[Extraction](extraction.md) for the configuration, schemas, extractors and the
stored records.

## Generate sources

```bash
biotope source generate .biotope/datasets/data/study.jsonld --out graph/sources
```

Generation gives every top-level record set, and every file no record set reads, a
package under `graph/sources/<manifest>/` with a schema, a `SOURCE` registration and
a placeholder loader. It creates missing files only and never rewrites an existing
schema, registration or loader; on a conflict it writes nothing. Only `biotope mv`
changes them: it rewrites a moved file's IDs and the pinned revision in its schema,
and a moved description's path in the registrations. Generation prints each package's
status (created, completed, current, drift, orphaned or conflict) and records every
contract revision in `.biotope/contracts/`. `--package` overrides the
manifest-derived root name; `--check` writes nothing and fails only when generation
would create or change a file. Removed sources leave orphan packages: exclude them,
then delete their directories.

`biotope source register <file.jsonld> --name <name>` registers a Croissant
description you wrote by hand for data that no bake describes, as the
[tutorial](tutorial.md) does. It refuses a name that is already registered.

After new data arrives, refresh with commands only:

```bash
biotope add --rebake data/study
biotope source generate .biotope/datasets/data/study.jsonld --out graph/sources
biotope graph check
biotope graph build
```

See [refresh after new data](project.md#refresh-after-new-data) for what changes and
how a project keeps new inputs from breaking its build.

`config` maintains annotation requirements and project metadata defaults; see
[shared annotation policies](cluster-compliance.md).

## Author and build

| Command                                                 | Behavior                                                                                |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `biotope graph scaffold`                                | Create `graph/` with empty registries and a pipeline to implement.                      |
| `biotope map --purpose ... --entity ... --relation ...` | Record research requirements.                                                           |
| `biotope map --show`                                    | Show the current purpose and requirements.                                              |
| `biotope graph check`                                   | Check the source inventory, drift, declarations, requirement bindings and Python types. |
| `biotope graph quality`                                 | Check and execute the pipeline, printing an assessment without export.                  |
| `biotope graph build`                                   | Check and execute, then replace `graph/build/` after a successful export.               |
| `biotope graph metagraph`                               | Write an offline topology viewer to `graph/metagraph.html`.                             |

Graph commands support `--json`; check, quality, build and metagraph also accept
`--graph <folder>`. Scaffold always creates `graph/` in the current directory and
refuses an existing path. It performs no initialization, baking or execution.
Build exports Neo4j import files by default; `--format sqlite` writes one SQLite
database, `graph.sqlite`, instead.

Check, quality and build discover the source packages statically, then load
`topology/__init__.py:TOPOLOGY` and `pipelines/build_graph.py:PIPELINE`, so
inventory findings are reported even when the pipeline cannot be imported. Check
does not invoke loaders or mappings. `build --out <dir>` builds elsewhere; a build
replaces a directory only when it recognizes every file in it. Metagraph imports
topology independently; `--out <html>` selects a different viewer path and
`--report <run.json>` adds matching-topology observations.

Quality and build each execute the declared scope once. Running both executes
twice. Warnings require interpretation; definition, execution and integrity
failures can fail an operation. See [typed projects](mapping.md)
for authoring and [report formats](commands_sidenotes.md) for JSON details.

## Track and review

| Command                         | Purpose                                                                              |
| ------------------------------- | ------------------------------------------------------------------------------------ |
| `biotope status`                | List the descriptions and mark those whose source packages pin another revision.     |
| `biotope check-data`            | Read source bytes to verify recorded checksums.                                      |
| `biotope mv`, `biotope rm`      | Move or remove tracked data and update the descriptions; `mv` also updates packages. |
| `biotope queue`, `biotope mark` | Inspect and maintain coarse `raw`, `processed` and `mapped` states.                  |

Biotope never writes to git: commit `.biotope/`, `graph/`, annotation files and
extracted records with your own git commands. Commands that write a file the
project must commit warn when git ignores it. `mv` works without git; `rm` can
delete source data. Queue states do not certify graph validity. Build outputs can
be archived separately without changing tracked source data.

For removed commands and options, see [migration](migration.md).
