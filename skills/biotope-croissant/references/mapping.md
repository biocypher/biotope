# Mapping grammar

A mapping file binds the slots you declared (`biotope map --entity/--relation`) to real record sets and fields in one dataset's Croissant manifest. One file per logical dataset, under `mappings/<stem>.mapping.yaml`. `build` streams every mapping and deduplicates nodes by id across files.

biotope does **not** infer which record set is which entity or which field is the id — you decide that and write it. Ground every pick in the field catalogue from `biotope map inspect <croissant> --json` or the scaffold's comment appendix; never invent a CURIE prefix, field, or entity type that the data doesn't have.

## Contents

- [File shape](#file-shape)
- [Entities](#entities)
- [Id selectors and transforms](#id-selectors-and-transforms)
- [Scans: row, explode, multi-axis](#scans)
- [Relations](#relations)
- [Reusable id selectors](#reusable-id-selectors)
- [Minimal vs rich bindings of the same entity](#minimal-vs-rich)
- [Validate](#validate)

## File shape

```yaml
croissant: .biotope/datasets/data/flights.jsonld
entities:
  <entity_name>: { ... }
relations:
  <relation_name>: { ... }
ids:                       # optional, reusable selectors
  <selector_name>: { ... }
```

## Entities

Each entity slot needs a `record_set`, a `scan`, and an `id`; `properties` is an optional map of `graph_property: source_field`.

```yaml
entities:
  book:
    record_set: books
    scan: row
    id:
      field: isbn
      transform: as_curie
      args: { prefix: isbn }
    properties:
      title: title
      year: year
```

A `properties` value is normally a column name (`title: title`). For a constant that's the same for every row — e.g. a fixed ontology id or a provenance tag — use a `value:` literal instead of inventing a column:

```yaml
    properties:
      title: title
      source_db: { value: "SourceDB" }
```

## Id selectors and transforms

A selector picks a value from a row in one of three mutually exclusive ways — `field` (read a column), `use` (a reusable named selector), or `value` (a literal constant) — plus an optional `transform`:

- `passthrough` (default) — use the field value as-is.
- `as_curie` — prefix the value into a CURIE: `args: { prefix: iata }` turns `ABE` into `iata:ABE`. Use this to put every source's ids into one namespace.
- `hash_id` — hash the field(s) into a stable synthetic id when no natural id exists.

The id is what makes two emissions the same node. If the same real-world entity appears in several sources, mint its id **identically** everywhere (same field semantics, same transform, same prefix) so BioCypher dedups it. Mismatched id construction is the most common cause of dropped edges and duplicate nodes — see `reliability.md`.

## Scans

`scan` controls how rows of a record set become graph elements.

- `scan: row` — one element per row (the common case).
- `scan: {explode: <field>}` — one element per item of an array-valued field. The exploded element is referenced as `field: "$item"`, **not** the array's name. The field name selects the array; `$item` names each element inside the scan. Sibling row columns are still addressed by their plain names.
- `scan: {explode: {<axis>: <field>, ...}}` — multi-axis explode. Each element is exposed as `field: "$<axis>"` (e.g. axis `author` → `field: "$author"`).

```yaml
entities:
  topic:
    record_set: services
    scan: { explode: edam_topics }              # array of scalar strings
    id: { field: "$item", transform: as_curie, args: { prefix: edam } }
```

### Array of structs — reach inside each element with `$item.<subfield>`

When the exploded array holds **objects, not scalars** (the common shape in nested JSON — e.g. a `node` record with `events: [{id: ...}, ...]`), `$item` is the whole struct. Address a field on it with a dot path: `field: "$item.id"`. This is the single most-missed piece of the grammar; without it you can't build a relation off a nested array of objects.

```yaml
# node records each carry events: [{id, role}, ...]
relations:
  node_organizes_event:
    record_set: nodes
    scan: { explode: events }                   # array of {id, role} structs
    source: { entity: node,  field: node_id,      transform: as_curie, args: { prefix: node } }
    target: { entity: event, field: "$item.id",   transform: as_curie, args: { prefix: event } }
    properties:
      role: "$item.role"                         # sibling sub-fields of the same element
```

For multi-axis explode the same dotting applies per axis: `field: "$<axis>.<sub>"` (e.g. `field: "$event.id"` for axis `event`). `biotope map preview` resolves the real type of each named sub-field. One constraint: `$item` (and `$item.<sub>`) is **not** valid inside a `where:` clause; filter on plain row columns instead.

## Relations

A relation names its `source` and `target` endpoints; each endpoint names the referenced `entity` and a selector that mints the **same id** that entity uses elsewhere. Optional `properties` attach edge attributes.

```yaml
relations:
  book_written_by_author:
    record_set: authorships
    scan: row
    source: { entity: book,   field: isbn,        transform: as_curie, args: { prefix: isbn } }
    target: { entity: author, field: author_id,   transform: as_curie, args: { prefix: orcid } }
    properties:
      role: contribution_role
```

Edge-level facts that aren't nodes (a tissue, a species, a comparison label) are best kept as relation `properties`, not promoted to entities — promoting them creates orphan nodes unless every value is independently sourced and linked.

If a relation you declared has no supporting field in the data, mark it deferred rather than faking a binding: `biotope map defer-relation <mapping> <relation>`. `build` skips deferred relations honestly and counts them; `undefer-relation` reverses it when the data arrives.

## Reusable id selectors

Define a selector once under top-level `ids:` and reference it with `use:` so an entity and the relations that point at it stay in lockstep:

```yaml
ids:
  author_curie: { field: author_id, transform: as_curie, args: { prefix: orcid } }

entities:
  author:
    record_set: authors
    scan: row
    id: { use: author_curie }
relations:
  book_written_by_author:
    record_set: authorships
    source: { entity: book,   use: isbn_curie }
    target: { entity: author, use: author_curie }
```

## Minimal vs rich

Same entity: rich binding in one mapping (full properties), minimal in another (id only). Both mint the id identically. BioCypher merges into one node.

**Per-file rule:** every relation endpoint's `entity` must appear under `entities:` in **that same file** — add a minimal stub if needed.

## Shared entities

If multiple record sets reference the same entity type (e.g. a tag, category, or ontology term), emit that entity from **each** record set that contributes edges to it — not only from one "primary" source. Otherwise edges target ids with no matching node → orphans at build.

Pick the record set with the richest linkage when one source embeds references another only holds a summary table.

## Validate

```bash
biotope map preview --json
```

`preview` checks YAML structure and field existence — **not** whether relation targets will resolve to emitted nodes. Check `unresolved_slots`, `findings`, and `sample_edge_tuples`. Orphan detection requires build + `biotope view` (`build_metrics.json`).
