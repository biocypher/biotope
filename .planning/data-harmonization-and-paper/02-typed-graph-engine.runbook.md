# Test the typed graph workflow

Run the small [repository example](../../docs/tutorial.md) first to learn the
commands and expected output. Then use the steps below in Daria and INTRAC.
Metadata review covers all `raw`; graph construction uses a selected, agreed subset.

## 1. Set up the project

Choose one project:

```bash
# Daria
cd /Users/vlad/Projects/virtual-human-dev/daria_mvp/data

# Or INTRAC: the working copy named in spec 2's technical notes
cd /Users/vlad/Projects/virtual-human-dev/usecases/intrac_260731
```

Install the local packages in the chosen project:

```bash
BIO=/Users/vlad/Projects/virtual-human-dev/biotope
BAKER=/Users/vlad/Projects/virtual-human-dev/croissant-baker
test -d .venv || uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -e "$BAKER" -e "$BIO[graph]"
source .venv/bin/activate
python -c 'import biotope, croissant_baker; print(biotope.__file__); print(croissant_baker.__file__)'
test -d .biotope || biotope init . --no-prompt
biotope map --show
```

## 2. Review or restore source descriptions

```bash
biotope add raw
```

For Daria, also describe the context workbook if it has no current manifest:

```bash
biotope add context/darias_input.xlsx
```

The current local Baker has no Excel handler, so this workbook is expected to
report `SKIP / No handler` and produce an empty manifest. Review its sheets with
your usual tools, author `.biotope/reviews/darias_input.jsonld`, then use the
registration route below with `--name context/darias_input --replace`.
An empty inspection is a coverage gap, not a usable source contract.

Read progress, coverage and warnings. Do not repeatedly rebake unchanged data.
A full-directory bake writes `.biotope/datasets/raw.jsonld`; earlier per-dataset
scans may instead have several manifests under `.biotope/datasets/raw/`.

For a full-directory manifest:

```bash
mkdir -p .biotope/reviews
biotope map inspect .biotope/datasets/raw.jsonld > .biotope/reviews/raw-fields.txt
biotope map inspect .biotope/datasets/raw.jsonld --json > .biotope/reviews/raw-fields.json
less .biotope/reviews/raw-fields.txt
```

Press `q` to leave `less`. With multiple manifests, inspect the selected ones by
their actual paths. Compare a few known fields, sheets, types and container shapes
using your usual tools. Account for unsupported files and partial descriptions.

Corrections or manually described inputs enter managed metadata through:

```bash
# Substitute the reviewed file and its managed dataset name.
biotope source register .biotope/reviews/study.jsonld --name raw/study \
  --reason "Evidence used and remaining gaps" --replace
```

Omit `--replace` for a new description. Curated and annotated manifests block
rebaking. When the inputs change, make a fresh description without overwriting them:

```bash
biotope add raw --bake-to .biotope/reviews/raw-fresh.jsonld
```

Use a new output filename each time. Compare this review file with the curated
manifest, carry over supported corrections, then register the reconciled result
under the same managed name (`raw` for this example). Relative data locations stay
anchored to the original input. Manual metadata does not establish a loader.
Replacement reports dropped keys, record-set/field IDs and curation notes before
writing. Review that report; the command replaces rather than merges metadata.
No new Zarr reader is needed for this test.

## 3. Author a selected build with the agent

Create the graph workspace once, from the project root:

```bash
biotope graph scaffold
```

If `graph/` already exists, reuse it. The scaffold writes boilerplate only; it
neither scans data nor builds a graph. Keep graph code, dependencies, notes and
helper tools inside it. Do not initialize another Biotope project inside `graph/`.
Its README explains the inactive typed examples; adapt these to reviewed source
contracts and purpose. Actual source generation remains a separate command and
creates missing per-source registration and loader files. Select `SOURCES`,
`TOPOLOGY` and `MAPPINGS` in their folders' `__init__.py` files.

Install the current skill, then start Claude Code from the activated terminal:

```bash
mkdir -p .agents/skills
ln -sfn "$BIO/skills/biotope-croissant" .agents/skills/biotope-croissant
claude
```

Use this prompt:

```text
Apply the biotope-croissant skill. Review the existing descriptions for all raw data. Reuse completed scans and account for unsupported or partially described sources. Here's the purpuse:
"""
I want a graph that brings together our cardiometabolic differential-expression datasets and their study metadata. It should keep gene-level measurements linked to disease, study, tissue, species, cell type and comparison, with log-fold change, direction, p-value and adjusted significance. Where full results are available, it should preserve non-significant measurements as well as significant ones so I can tell a measured null from data that are absent.

I'd want it to cover AF versus sinus rhythm in the in-house left atrial appendage cohort and the Hill and LeBlanc AF studies, thrombosis in clot versus blood, human MI across blood time points, mouse MI from steady state through the post-infarct time course, and sepsis versus control in blood. The graph should include all annotated cell types, particularly cardiomyocytes, adipocytes, mast cells, lymphocytes and T cells, monocytes, macrophages, neutrophils and platelets. I need to compare genes and cell-type response patterns within and across diseases, tissues, time points and AF studies; link mouse and human genes through the full many-to-many ortholog mapping; and trace each result to its study title, creator, publication and source dataset. Metadata-only records such as the atherosclerosis atlas and VTE study should remain identifiable without implying that differential-expression results exist.
"""

Curate metadata where evidence supports it. Use the existing graph/ scaffold, generate source dataclasses there, and author Python topology, source-local loaders, mappings and an explicit pipeline. Keep all graph-specific artifacts under graph/.
Use established parsing libraries. Include source evidence from both sides of joins. Create an import-safe entry point graph.pipelines.build_graph:PIPELINE and run definition/type checks. Continue through the selected BioCypher file build, stopping before database import.
```

INTRAC's earlier `purpose.txt` and `competency_questions.csv` are in the original
`usecases/intrac_260731` directory if the working copy lacks them. Treat them as
existing research context, not permission to invent new scientific choices.

The agent should show the actual generation commands for the selected manifests:

```bash
biotope source generate .biotope/datasets/raw.jsonld --out graph/sources/raw/schema.py
```

This example applies to a full-directory manifest. Use the agent's actual paths
for a project with several source modules. Read a generated class, its sibling
loader, one mapping and the pipeline. Confirm which code reads values and which
code defines transformations.

## 4. Check and execute yourself

```bash
biotope graph check graph.pipelines.build_graph:PIPELINE --json > .biotope/reviews/definitions.json
biotope graph build graph.pipelines.build_graph:PIPELINE --out graph/build/review-1
```

The first command reads metadata and import-safe Python. It does not invoke
loaders. To verify payload independence, ask the agent to copy only metadata,
intent and authored/generated Python into a scratch project and run the same
check there. Do not move, rename or chmod the real raw data.

The build explicitly opens selected inputs through project loaders. It writes:

| File                                                            | Review                                                |
| --------------------------------------------------------------- | ----------------------------------------------------- |
| `graph/build/review-1/run.json`                                 | Completion, scope, revisions, settings and exclusions |
| `graph/build/review-1/biocypher/*-header.csv` and `*-part*.csv` | Actual node/edge IDs, values and types                |
| `graph/build/review-1/topology.json`                            | Stable concept IDs and export-label mapping           |
| `graph/build/review-1/provenance.jsonl`                         | Input evidence for each node/edge                     |

Compare outputs with `.biotope/reviews/plan.md`. Trace a few nodes and edges
back to row/key/container references, including joined and deduplicated objects.
These references identify all inputs of the producing mapping call, not per-property
lineage. Review exclusion counts and their bounded evidence samples. A failed run remains failed in `run.json`; do not accept a
partial output directory as a complete graph. Existing run directories are not
overwritten; choose a new name for each run.

## 5. Exercise edits and repeat

On a copy or a reversible edit, ask the agent to demonstrate a renamed property,
a wrong value type and a swapped endpoint ID. The real checker should report
useful errors; repair them. Then change a source description, regenerate, and
repair affected loaders/mappings. Check that curated metadata and authored files
survive. Change a topology property and repeat the check/repair cycle.

Run a fixed small build twice with identical inputs/settings. The `graph_digest`
values in the two run records should agree. A multiple-input preparation step
must be demonstrated here or in the small repository example. It need not cover
all fields, matrices or all possible joins.

Record the results in `.biotope/reviews/notes.md`:

- [ ] Actual project directory and metadata scope recorded, including omissions.
- [ ] Selected task, identity rules and expected outputs agreed before execution.
- [ ] Generated contracts and separate loaders/mappings understood.
- [ ] Type failures and metadata/topology revision repair demonstrated.
- [ ] Definition checks passed with only metadata and Python in a scratch copy.
- [ ] Output values, relations, exclusions and provenance reviewed against the plan.
- [ ] Repeated deterministic content agreed; limits and remaining choices recorded.

For each defect, include command, input, expected/observed behavior and relevant
output. Repeat on the other project. Send the notes for B9 acceptance; automated
example tests do not replace your scientific review.

## 6. Clean up outputs

After the build and agent session stop, archive only generated runs and review
notes. This keeps raw data, purpose, curated metadata and all authored Python:

```bash
mkdir -p graph/review-backups
archive=$(mktemp -d "$PWD/graph/review-backups/typed-run-XXXXXX")
for path in graph/build .biotope/reviews; do
  if [ -d "$path" ]; then mv "$path" "$archive/"; fi
done
echo "Saved outputs in $archive"
```

Do not use the old Spec 1 cleanup list: it archived mappings and managed metadata.
Do not use `biotope rm raw`. Keep generated source modules with their metadata
until review; regenerate them explicitly when needed.
