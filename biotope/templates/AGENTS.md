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

Populate the project document via `biotope map` intent flags — never edit
YAML by hand:

```bash
biotope map --purpose "..." \
            --entity gene --entity disease --entity drug \
            --relation "which drugs target which genes" \
            --relation "which genes are associated with which diseases"
```

When any intent flag is present, `biotope map` runs **non-interactively**: it
writes to `.biotope/project.yaml` (or `./project.yaml` if the project was
initialised with `--visible`) and exits. With no flags, it would launch the
interactive wizard — agents should always use flags instead.

`--entity` and `--relation` accept **free text**. Use a short label if the
schema vocabulary is already settled (`drug_targets_gene`); otherwise capture
the user's wording verbatim (`which drugs target which proteins`) — keys are
normalised to `snake_case` automatically. Run `biotope map --show` at any time
to print the current intent plus mapping progress.

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

## Author the mapping

biotope does **not** infer which record set should be a `gene` or which field
is the `id`. You do.

### 1. Generate an unresolved scaffold

```bash
biotope map scaffold .biotope/datasets/<name>.jsonld
```

This writes `mappings/<name>.mapping.yaml` with one slot per entity and
relation you declared via `biotope map --entity / --relation`, plus a YAML
comment appendix listing every record set, field kind, identifier-like
candidate, explode-eligible array, and a few sample rows. The slots
themselves are unresolved placeholders — they don't even pick a record set.

### 2. Inspect (optional, JSON form for agents)

```bash
biotope map inspect .biotope/datasets/<name>.jsonld --json
```

Use this to enumerate record sets and fields when the appendix isn't enough
context to decide. Never run `biotope build` first hoping for an error
message — `inspect` and `preview` are the canonical evidence views.

### 3. Edit the YAML directly

Each entity slot needs `record_set`, `scan` (`row` or `{explode: <field>}`),
and an `id` selector. Selectors take `field`, optional `transform`
(`passthrough`, `as_curie`, `hash_id`), and optional `args`. Reusable ID
selectors live under top-level `ids:` and can be referenced via `use:`.

```yaml
entities:
  gene:
    record_set: targets
    scan: row
    id:
      field: ensembl_id
      transform: as_curie
      args: { prefix: ensembl }
    properties:
      symbol: approved_symbol
```

Relation endpoints must name the referenced entity:

```yaml
relations:
  drug_targets_gene:
    record_set: target_drug
    source: { entity: drug,  field: drug_id, transform: as_curie, args: { prefix: chembl } }
    target: { entity: gene,  use:   gene_curie }
```

### 4. Validate before building

```bash
biotope map preview --json
```

Lists unresolved slots, validation findings, the projected BioCypher schema,
and sample emitted tuples. Iterate until `unresolved_slots` is empty and
`findings` contain no errors. Cross-mapping equivalences are still proposed
with:

```bash
biotope propose-alignment mappings/*.mapping.yaml
```

Do not invent CURIE prefixes or entity types — capture what the user actually
said, or leave the slot for them to fill.

## Build the graph

```bash
biotope build
```

This invokes the deterministic backend: read mappings + optional alignment,
stream rows via DuckDB, write a runnable BioCypher project. `build` is
**strict** — it refuses to compile any mapping with unresolved slots or the
legacy `nodes`/`edges` schema. The output is `build/config/schema_config.yaml`
(generated with `namespace` and autogenerated `input_label`), one
`build/generated/<stem>/adapter.py` per mapping, and
`build/create_knowledge_graph.py` — plain Python and YAML the user can commit,
version, and rebuild without you.

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
