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
                 --relation "which drugs target which genes" \
                 --relation "which genes are associated with which diseases"
```

`biotope describe` writes to `.biotope/project.yaml` (or `./project.yaml` if
the project was initialised with `--visible`). It is the agent-side equivalent
of an editor: the only canonical way to record content-level intent.

`--entity` and `--relation` accept **free text**. Use a short label if the
schema vocabulary is already settled (`drug_targets_gene`); otherwise capture
the user's wording verbatim (`which drugs target which proteins`) and let
downstream commands resolve it heuristically. Running `biotope describe` with
no flags prints the current state plus a reminder of available flags — useful
as a status check at any point.

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
infer (license, creator, creator email, description, access restrictions,
legal obligations, collaboration details, and any RAI metadata) as flags.

If the dataset is a directory, `biotope add <dir>` recurses automatically and
also writes `<dir>/.biotope.yaml` for bulk human review. After editing that
scaffold, apply it with:

```bash
biotope annotate apply <dir>
```

You can override one field across the whole apply step with:

```bash
biotope annotate apply <dir> --set creator="Open Targets Consortium"
```

To find datasets the user does *not* yet have:

```bash
biotope discover
```

This consults the BioCypher-adapter registry against the
`required_entities` you wrote into `project.yaml` and ranks candidates.

## Propose mappings and alignments

```bash
biotope propose-mapping .biotope/datasets/<name>.jsonld

biotope propose-alignment mappings/*.mapping.yaml
```

Both commands emit YAML for the human to review. Show the user the diff before
moving on. Do not invent CURIE prefixes or entity types — leave the defaults
unless the user has told you which BioCypher types to target.

`biotope propose-mapping` writes commented review scaffolds. Use the inline
field inventory and sample rows to explain what a record set contains before
you rewrite `type`, `id`, `properties`, or `where`.

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
- Prefer `biotope annotate apply` over interactive editing when a dataset
  already has a `.biotope.yaml` scaffold.
- Never bypass git-tracked metadata — `biotope add`, `biotope commit`,
  `biotope mv` exist for that.
- If a command's output looks wrong, fix the inputs (purpose, mapping,
  alignment) and re-run. Do not patch generated files by hand.
- Keep `purpose:` in `.biotope/project.yaml` honest. It's the single sentence
  someone reading this project a year from now will rely on.
