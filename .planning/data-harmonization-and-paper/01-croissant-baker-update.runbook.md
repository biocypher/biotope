# Test Biotope on Daria and INTRAC

Scan the raw data, review its description, then create and check mappings. Stop
before graph construction. Repeat these steps in each project.

For a fresh test, archive previous outputs with step 6 first. After setup, review a completed
scan by continuing at step 3. Earlier sample results are in the
[runbook notes](01-croissant-baker-update.runbook_sidenotes.md).

## 1. Open the project and install local packages

For Daria:

```bash
cd /Users/vlad/Projects/virtual-human-dev/daria_mvp/data
```

For INTRAC:

```bash
cd /Users/vlad/Projects/virtual-human-dev/biotope-bench/data/intrac_260731/workspace
```

Both projects are already initialized. Run this setup in the chosen directory:

```bash
BIO=/Users/vlad/Projects/virtual-human-dev/biotope
BAKER=/Users/vlad/Projects/virtual-human-dev/croissant-baker
test -d .venv || uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -e "$BAKER" -e "$BIO"
source .venv/bin/activate
biotope --version
python -c 'import biotope, croissant_baker; print(biotope.__file__); print(croissant_baker.__file__)'
```

The two printed import paths should point into the local checkouts above.

## 2. Scan all raw data

```bash
biotope add raw --rebake
```

This scans the full `raw` directory recursively. `--rebake` also lets you repeat
the scan. Run it directly in the terminal to see live progress.

Expect a preparation message and spinner while baker loads its handlers and
finds files. Counts appear after the first file finishes, then advance as files
finish. Large files can take time because baking includes checksums. Review the
final summary and named warnings for partial, unsupported or failed inputs.
Zipped Zarr is tracked without structural fields; Zarr support remains out of scope.

For Daria, also add the context workbook outside `raw`:

```bash
biotope add context/darias_input.xlsx --force
```

`--force` regenerates an individual file's description. The outputs are:

| Path                                            | What it contains                            |
| ----------------------------------------------- | ------------------------------------------- |
| `.biotope/datasets/raw.jsonld`                  | Croissant metadata for the entire raw tree  |
| `raw/.biotope.yaml`                             | Editable metadata annotations for that tree |
| `.biotope/datasets/context/darias_input.jsonld` | Daria's context workbook metadata           |
| `mappings/`                                     | Mapping definitions created in step 4 or 5  |

## 3. Review the description

Save readable and JSON versions so you can inspect a large result comfortably:

```bash
mkdir -p integration-review
biotope map inspect .biotope/datasets/raw.jsonld > integration-review/raw-fields.txt
biotope map inspect .biotope/datasets/raw.jsonld --json > integration-review/raw-fields.json
less integration-review/raw-fields.txt
```

Press `q` to leave `less`. For Daria's workbook, also run:

```bash
biotope map inspect .biotope/datasets/context/darias_input.jsonld
```

Compare a few known source files with their descriptions: sheet and column
names, types, HDF5 paths and shapes, image dimensions. Use your usual file tools
for these checks. Confirm that warnings explain omissions. Biotope shows
structure, not sample values. Mappings should use record-set IDs when names repeat.

## 4. Define purpose and mappings

```bash
biotope map --show
biotope map
biotope map preview
```

The first command shows the current purpose and mapping status. In the wizard,
use **edit intent** to review the purpose, entities and relations, then bind the
required slots to declared source fields. The wizard saves mappings under
`mappings/`. You can also edit those YAML files directly.

`preview` checks definitions without reading source values. Resolve reported
errors and unfinished bindings. Empty stubs are inactive and can pass checks:
also confirm that the intended entities and relations have bindings.

## 5. Try the agent

From the same project directory and activated environment:

```bash
mkdir -p .agents/skills/biotope-croissant
cp -R "$BIO/skills/biotope-croissant/." .agents/skills/biotope-croissant/
claude
```

Give Claude Code this prompt:

> Apply the biotope-croissant skill to this project. Review the existing metadata
> for the full raw directory and, for Daria, the context workbook. Explain what
> was described and what is missing. Help me define the purpose, target entities
> and relations, and mappings from declared fields. Ask about unresolved research
> or identity choices. Run structural mapping checks and stop before graph
> construction or writing loaders. Reuse the completed scan unless we need to
> investigate a defect.

Record the outcome in `integration-review/notes.md`:

- [ ] Startup, progress and final coverage are understandable.
- [ ] Spot-checked metadata matches the sources; omissions are explained.
- [ ] Mapping checks behave as expected and purpose coverage was reviewed.
- [ ] The agent understands the metadata and limitations and can help map it.

For a defect, include the exact command, input path, expected and observed result,
and relevant output. Keep the notes and mappings until reviewed.

## 6. Clean up test outputs

Run this from the project root after the scan and agent session have stopped.
It moves generated metadata, mappings, review notes and the raw sidecar into a
unique backup directory. Raw data, project purpose, configuration and the installed
environment stay in place.

```bash
mkdir -p review-backups
backup=$(mktemp -d "$PWD/review-backups/run-XXXXXX")
for output in .biotope/datasets mappings integration-review; do
  if [ -d "$output" ]; then mv "$output" "$backup/"; fi
done
if [ -f raw/.biotope.yaml ]; then
  mv raw/.biotope.yaml "$backup/raw.biotope.yaml"
fi
mkdir -p .biotope/datasets mappings
echo "Saved previous outputs in $backup"
```

To test again, return to step 2. To restore previous work, move the saved folders
back to their original locations before generating replacements. Do not use
`biotope rm raw` for this cleanup: that command also deletes source data.
