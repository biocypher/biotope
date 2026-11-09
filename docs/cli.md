# CLI reference

Run each command from the project folder as `uv run --project graph biotope …`. Commands that write a report take `--json` and then write one JSON document to stdout. `biotope <command> --help` lists a command's arguments and options.

## Project and data

| Command | What it does |
| --- | --- |
| `init` | Creates a Biotope project in the folder NAME, or in the current folder with NAME `.`. |
| `add` | Describes data files or folders as datasets and creates the annotation file of each. |
| `annotate set` | Writes KEY=VALUE pairs into the annotation file of a dataset. |
| `annotate validate` | Validates a Croissant metadata file. |
| `config set-project-metadata` | Sets the project metadata, such as the creator and licence, that `add` applies to every dataset. |
| `config show-project-metadata` | Shows that project metadata. |
| `mv` | Moves a tracked file or folder and updates every description and source package that names it. |
| `rm` | Removes a dataset or a file from Biotope, with its data unless `--keep-data` is given. |
| `status` | Lists the dataset descriptions and marks those whose revision differs from the one their source package pins. |
| `check-data` | Compares the data files with the checksums their descriptions record and reports each changed file. |
| `mark` | Sets the status of a dataset: raw, processed or mapped. |
| `queue` | Shows every dataset grouped by its status. |
| `map inspect` | Shows the sources and fields a description declares, without reading the data. |

## Extraction

| Command | What it does |
| --- | --- |
| `extract try` | Runs one extraction on the given files and shows the records with their evidence. Nothing in the project changes. |
| `extract run` | Runs the listed extractions, stores their records in `data/extracted/<name>.jsonl` and registers each records file as a dataset. An unchanged document is not extracted again. |

## Sources and graph

| Command | What it does |
| --- | --- |
| `source generate` | Creates the missing source packages for one description, and reports drift, orphans and conflicts. |
| `source register` | Registers a Croissant description written by hand, for data that `add` does not describe. |
| `graph scaffold` | Creates the `graph/` workspace. |
| `graph check` | Checks the definitions and Python types without running loaders or mappings. |
| `graph quality` | Runs the loaders and mappings and prints measurements of the graph, without exporting it. |
| `graph build` | Runs the loaders, mappings and quality checks, then exports the graph to `graph/build/`. |
| `graph metagraph` | Writes `graph/metagraph.html`, a viewer of the node and edge types; `--report` adds the counts of a build. |
