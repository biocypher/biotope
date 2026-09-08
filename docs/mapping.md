# Mapping reference

A mapping binds the entities and relations you declared
(`biotope map --entity/--relation`) to real record sets and fields in one
dataset's Croissant manifest. Write one file per logical dataset under
`mappings/<stem>.mapping.yaml`. Mappings are definitions; this iteration does not execute them.

Biotope never infers which record set is an entity or which field is an id. You
decide and write it. Ground every choice in the field catalogue from
`biotope map inspect <croissant> --json` or the scaffold's comment appendix.
Use declared fields and explain chosen identifier namespaces and target types.

Generate a starting point with `biotope map scaffold <croissant>`, then fill in
the slots.

Unnamed fields appear under their declared field ID. Do not infer their meaning
from that ID; record any unresolved interpretation.

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

Use the record-set `id` shown by inspection for `record_set`; display names are accepted only when unambiguous. Each entity needs a `record_set` and an `id`; `scan` defaults to `row`. `properties` is an
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
semantics, transform, and prefix) for consistent identity in later project code. Mismatched id
construction is the most common cause of dropped edges and duplicate nodes.

Preview infers the namespace of a literal CURIE such as `geo:GSM1`; an explicit
entity `namespace:` overrides that inference. No transform is executed.

## Scans

`scan` declares intended row or array handling for future project-owned loaders.

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

Choose entities versus properties according to the agreed research schema.
Do not change that choice merely to simplify a binding.

If a declared relation has no supporting field, defer it instead of faking a
binding:

```bash
biotope map defer-relation <mapping> <relation>
```

`undefer-relation` reverses the declaration when the data supports the relation.

Deferred relations remain visible as known gaps in preview and the wizard.
They appear in `deferred_slots` per mapping and `global.slot_deferred` in JSON.
They do not count as resolved bindings or fail structural checks by themselves.
The defer/undefer commands preserve YAML comments. If an alias would also change
another relation, the file stays unchanged and the command asks for an explicit edit.

For a constant relation endpoint, define a selector under `ids:` and refer to
it with `use:`. A direct endpoint `value:` is not part of the mapping grammar.

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

If several record sets reference the same entity type, plan that entity binding in
each record set that contributes edges to it, not only from one primary source.
Whether those identifiers match source values must be checked in later project work.

## Validate

```bash
biotope map preview --json
```

This checks metadata and mapping definitions. Inspect `unresolved_slots`,
`findings`, and the proposed schema. Errors or partially filled bindings produce exit
code 1; warnings still need review. Empty stubs are inactive in this model and
can pass without producing any schema. Compare the resolved slots with project
intent; a passing result alone does not establish purpose coverage. A passing check does not validate source
values, identifiers, joins, filters or transformations. Biotope provides no row
samples and does not execute these definitions. Stop here for this iteration.

Record unsupported fields and scientific choices explicitly. Do not manufacture
columns or change the user's schema just to make validation pass. Metadata-based
alignment suggestions are hypotheses for review, not verified identities.

Malformed mappings report their filename and offending field or YAML location.
