# Mapping reference

A mapping binds the entities and relations you declared
(`biotope map --entity/--relation`) to real record sets and fields in one
dataset's Croissant manifest. Write one file per logical dataset under
`mappings/<stem>.mapping.yaml`. `build` streams every mapping and deduplicates
nodes by id across files.

Biotope never infers which record set is an entity or which field is an id. You
decide and write it. Ground every choice in the field catalogue from
`biotope map inspect <croissant> --json` or the scaffold's comment appendix.
Never invent a prefix, field, or entity type the data does not have.

Generate a starting point with `biotope map scaffold <croissant>`, then fill in
the slots.

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

Each entity needs a `record_set`, a `scan`, and an `id`. `properties` is an
optional map of `graph_property: source_field`.

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

A property value is normally a column name. For a constant that is the same for
every row (a fixed ontology id, a provenance tag), use a `value:` literal
instead of inventing a column:

```yaml
    properties:
      title: title
      source_db: { value: "SourceDB" }
```

## Id selectors and transforms

A selector picks a value from a row in one of three mutually exclusive ways,
plus an optional transform:

- `field`: read a column.
- `use`: reference a reusable named selector (see
  [reusable selectors](#reusable-id-selectors)).
- `value`: use a literal constant.

Transforms:

- `passthrough` (default): use the value as-is.
- `as_curie`: prefix the value into a CURIE. `args: { prefix: iata }` turns
  `ABE` into `iata:ABE`. Use it to put every source's ids in one namespace.
- `hash_id`: hash the field(s) into a stable synthetic id when no natural id
  exists.

The id is what makes two emissions the same node. If the same real-world entity
appears in several sources, mint its id identically everywhere (same field
semantics, transform, and prefix) so BioCypher deduplicates it. Mismatched id
construction is the most common cause of dropped edges and duplicate nodes.

## Scans

`scan` controls how rows become graph elements.

- `scan: row`: one element per row (the common case).
- `scan: { explode: <field> }`: one element per item of an array-valued field.
  Reference the exploded scalar as `field: "$item"`, not the array's name.
  Sibling row columns keep their plain names.
- `scan: { explode: { <axis>: <field>, ... } }`: multi-axis explode. Each
  element is exposed as `field: "$<axis>"`.

```yaml
entities:
  topic:
    record_set: services
    scan: { explode: edam_topics }        # array of scalar strings
    id: { field: "$item", transform: as_curie, args: { prefix: edam } }
```

When the exploded array holds objects rather than scalars, `$item` is the whole
struct. Address a field on it with a dot path, `field: "$item.id"`:

```yaml
# node records each carry events: [{id, role}, ...]
relations:
  node_organizes_event:
    record_set: nodes
    scan: { explode: events }             # array of {id, role} structs
    source: { entity: node,  field: node_id,    transform: as_curie, args: { prefix: node } }
    target: { entity: event, field: "$item.id", transform: as_curie, args: { prefix: event } }
    properties:
      role: "$item.role"                  # sibling sub-field of the same element
```

For multi-axis explode the same dotting applies per axis (`field: "$event.id"`).
`$item` and `$item.<sub>` are not valid inside a `where:` clause; filter on
plain row columns instead.

## Relations

A relation names a `source` and `target` endpoint. Each endpoint names the
referenced `entity` and a selector that mints the same id that entity uses
elsewhere. Optional `properties` attach edge attributes.

```yaml
relations:
  book_written_by_author:
    record_set: authorships
    scan: row
    source: { entity: book,   field: isbn,      transform: as_curie, args: { prefix: isbn } }
    target: { entity: author, field: author_id, transform: as_curie, args: { prefix: orcid } }
    properties:
      role: contribution_role
```

Keep edge-level facts that are not nodes (a tissue, a species, a comparison
label) as relation `properties`. Promoting them to entities creates orphan
nodes unless every value is independently sourced and linked.

If a declared relation has no supporting field, defer it instead of faking a
binding:

```bash
biotope map defer-relation <mapping> <relation>
```

`build` skips deferred relations and counts them. `undefer-relation` reverses it
when the data arrives.

## Reusable id selectors

Define a selector once under top-level `ids:` and reference it with `use:` so an
entity and the relations pointing at it stay in lockstep:

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
    source: { entity: book,   use: isbn_curie }
    target: { entity: author, use: author_curie }
```

## Shared entities

Every relation endpoint's `entity` must appear under `entities:` in the same
file; add a minimal id-only stub if needed. The same entity can have a rich
binding in one mapping and a minimal one in another, as long as both mint the id
identically.

If several record sets reference the same entity type, emit that entity from
each record set that contributes edges to it, not only from one primary source.
Otherwise edges target ids with no matching node and become orphans at build.

## Validate and verify

```bash
biotope map preview --json
```

`preview` checks YAML structure and field existence. It does not check whether
relation targets resolve to emitted nodes, so a clean preview can still produce
orphaned edges. Confirm the graph after building:

```bash
biotope build
biotope view      # counts, orphaned edges, schema diff
```

`orphaned_count` (also in `build/biocypher-out/build_metrics.json`) must be 0. A
relation with far fewer edges than expected signals an id-namespace mismatch.

## Reliability

Most graph errors come from inconsistent ids or stale manifests. Follow these
rules before building:

- Pick one id column for each entity and use it in every source. Normalize
  disagreeing forms (`UBERON_0002107` vs `UBERON:0002107`) in a committed
  preprocessing step, and keep alternate ids as properties. Use an ontology
  namespace where one exists.
- Fix id mismatches in the source data. With canonical ids, the correct
  alignment set is usually empty. Treat `propose-alignment` output as
  hypotheses, and review each `reason` and `confidence` before applying it.
- Defer unsupported relations instead of fabricating data to satisfy a slot.
  The build can then report the relation as unsupported.
- Point `add` at the folder that represents one logical dataset. Give
  independent datasets separate manifests.
- When preprocessing changes columns, run `biotope add <dir> --rebake` before
  mapping the new fields.
