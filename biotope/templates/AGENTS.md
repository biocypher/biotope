# Agent instructions for this biotope project

You are working inside a `biotope` project — a Croissant-driven knowledge-graph
workspace. Always reach for the CLI; never edit configs by hand and never
import biotope's Python modules directly. Every action a user could take is
exposed as a flag on a biotope command.

## Start every session by orienting

Before any technical work, elicit the user's **competence questions** in their
own words:

1. What concrete biological or clinical questions should this graph answer?
2. What entities (genes, drugs, diseases, cohorts, …) are involved?
3. What relations between them matter?
4. Which datasets does the user already have on disk, and which would need to
   be discovered or generated?

You may already find some of these answers in `.biotope/project.yaml`. If so,
confirm them with the user before assuming they're current.

## Record what you learn

Populate the project document via flags — never edit YAML by hand:

```bash
biotope describe --purpose "..." \
                 --entity gene --entity disease --entity drug \
                 --relation gene_associated_with_disease \
                 --relation drug_targets_gene
```

`biotope describe` writes to `.biotope/project.yaml` (or `./project.yaml` if
the project was initialised with `--visible`). It is the agent-side equivalent
of an editor: the only canonical way to record content-level intent.

## Bring data in

For each dataset the user has on disk:

```bash
biotope add <path> \
  --license "CC-BY-4.0" \
  --creator "User Name" \
  --description "..."
```

`biotope add` runs croissant-baker on the file(s) to autogenerate the Croissant
JSON-LD in `.biotope/datasets/`. Pass the metadata that the baker *cannot*
infer (license, creator, access restrictions, legal obligations) as flags.

To find datasets the user does *not* yet have:

```bash
biotope discover
```

This consults the BioCypher-adapter registry against the
`required_entities` you wrote into `project.yaml` and ranks candidates.

## Propose mappings and alignments

```bash
biotope propose-mapping .biotope/datasets/<name>.jsonld \
  --out mappings/<name>.mapping.yaml

biotope propose-alignment mappings/*.mapping.yaml \
  --out alignment.yaml
```

Both commands emit YAML for the human to review. Show the user the diff before
moving on. Do not invent CURIE prefixes or entity types — leave the defaults
unless the user has told you which BioCypher types to target.

## Build the graph

```bash
biotope build
```

This invokes the deterministic backend: read mappings + optional alignment,
stream rows via DuckDB, write a runnable BioCypher project. The result is
plain Python and YAML the user can commit, version, and rebuild without you.

## Inspect and report

After every build:

```bash
biotope status      # are tracked files still consistent?
biotope view        # node and edge counts, schema diff
biotope benchmark   # quality / coverage metrics
```

Report counts and obvious anomalies back to the user. Never claim a build
"works" without `biotope view` confirming non-empty outputs.

## House rules

- Use flags, not interactive prompts. If you'd be tempted to run
  `biotope init --interactive`, prefer setting the flags directly.
- Never bypass git-tracked metadata — `biotope add`, `biotope commit`,
  `biotope mv` exist for that.
- If a command's output looks wrong, fix the inputs (purpose, mapping,
  alignment) and re-run. Do not patch generated files by hand.
- Keep `purpose:` in `.biotope/project.yaml` honest. It's the single sentence
  someone reading this project a year from now will rely on.
