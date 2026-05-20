# `biotope map`

Semantic mapping command group. Replaces the removed `biotope describe` (intent capture is now an intent flag on `map`) and the deprecated heuristic `biotope propose-mapping` (scaffolding is now `biotope map scaffold`).

The command never auto-picks a record set or fields. All semantic decisions are made by the human or copilot agent against deterministic inspection output.

## `biotope map` (bare)

- **No flags**: launches the guided wizard. The wizard prompts for the Croissant file or mapping if it can't auto-discover them, captures intent on first run if `project.yaml` is empty, walks each unresolved entity / relation slot in order, autosaves after every confirmed edit, and offers inline entity creation when a relation references a not-yet-defined entity.
- **Any intent flag present** — runs non-interactively (agent-friendly):

```bash
biotope map --purpose "..."       # replace project's purpose
biotope map --entity gene --entity disease       # append to required_entities
biotope map --relation gene_associated_with_disease
biotope map --source <path-or-url>
biotope map --notes "..."
biotope map --clear-entities --clear-relations --clear-sources
biotope map --show                # print intent + mapping progress
```

The wizard also offers a `--croissant <path>` and `--mapping <path>` option to pin which file to operate on.

## `biotope map inspect <croissant>`

Deterministic inspector for a Croissant dataset. For each record set: name, description, source, field inventory (with `scalar` / `array` / `struct` kind), identifier-like candidates, explode-eligible arrays, and sample rows rendered as vertical key-value blocks. `--json` produces a stable machine-readable form for agents.

## `biotope map scaffold <croissant>`

Emit an **unresolved** semantic mapping scaffold:

- top-level `croissant`, empty `ids`
- `entities` and `relations` keyed by `project.yaml`'s `required_entities` / `required_relations`, normalised to `snake_case`
- a YAML comment appendix at the bottom with the inspector output (record sets, fields, sample rows) so a human or agent can edit the file without re-running inspection

Defaults to `mappings/<croissant-stem>.mapping.yaml`; pass `--out` or `--stdout` to override.

## `biotope map preview [<mapping>]`

Validate a (partial) mapping and project its outputs. Tolerant of unresolved slots — reports them rather than crashing. Output:

- resolved vs unresolved slots
- validation findings (missing record sets, unknown fields, invalid explode targets, illegal `$item` placement, unresolved endpoints)
- projected BioCypher schema (`schema_term`, `input_label`, `namespace`, `represented_as`, properties, edge source/target)
- sample emitted tuples from resolved sections

`--json` for agent consumption. The wizard reuses this engine after every confirmed edit.

## Agent workflow

Agents bypass the wizard and instead:

1. Set intent — `biotope map --entity ... --relation ...`.
2. Generate scaffold — `biotope map scaffold <croissant>`.
3. Inspect — `biotope map inspect <croissant> --json`.
4. Edit `mappings/*.mapping.yaml` directly.
5. Validate — `biotope map preview --json`.
6. `biotope build`.

::: biotope.commands.map
