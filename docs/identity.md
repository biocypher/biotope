# Identity and precedence

A project declares which keys identify each kind of entity and which source wins
for each field. Mappings emit one copy of an entity per source record. After the
pipeline has run, biotope merges the copies that share a value of a declared key,
or that a project matcher linked, into one entity; takes each field from the first
source in its declared order; resolves relation endpoints given by key values; and
lists every contradiction, conflict and automatic merge it found. Biotope judges no
equivalence itself: it merges only on the keys you declared and on the links your
matcher wrote. It stores nothing between builds.

Both declarations live in `graph/alignment/__init__.py`, next to the topology, and
the pipeline registers them:

```python
from biotope.graph import Identity, Key, Precedence

from ..sources.genes.study_a import SOURCE as STUDY_A
from ..sources.genes.study_b import SOURCE as STUDY_B
from ..sources.people.directory import SOURCE as DIRECTORY
from ..sources.people.roster import SOURCE as ROSTER
from ..topology.gene.node import Gene
from ..topology.person.node import Person


IDENTITIES = (
    Identity(Gene, keys=(Key("ensembl", single=True),), natural="ensembl"),
    Identity(Person, keys=(Key("roster", single=True), Key("orcid", single=True), Key("emails"))),
)

PRECEDENCE = (
    Precedence(Gene, fields={"symbol": (STUDY_A, STUDY_B)}),
    Precedence(Person, fields={"name": (ROSTER, DIRECTORY)}, combine=("emails",)),
)
```

```python
PIPELINE = Pipeline(..., identities=IDENTITIES, precedence=PRECEDENCE)
```

`biotope graph scaffold` writes both tuples empty and wires them into the pipeline.
A complete project with genes of two studies and people from four sources is in
`tests/fixtures/identity/` in the biotope repository.

## Copies and record IDs

A mapping emits an entity as before, as an instance of its topology class. For a
concept with an identity declaration, each instance is a copy that one source
record gives, and its `id` is that record's ID, such as `roster:recA1` or
`study_a:3`. The record ID is a namespaced identifier like any other: a prefix, a
colon and no whitespace. For a B1 extracted record, prefix its ID, for example
`profile:data/pages/ilse.html`. Copies with the same record ID are one record.

Copies of a concept without an identity declaration merge by their `id`, as in
0.10, and the `id` is the entity's ID.

## Identity declaration

`Identity(concept, keys, natural=None)` names the keys that identify a node
concept's records.

- **Keys are fields.** `Key("orcid")` reads the copy's `orcid` field. A `str` or
  `str | None` field gives at most one value, a `list[str]` field several. Empty
  strings and `None` give none. A key can be a natural key, such as an Ensembl ID
  or a DOI, an alias, such as an email or an ORCID, or another source's record ID
  that a record carries, such as a directory row that names its roster record.
- **Single or multi-valued.** `Key("orcid", single=True)` says an entity holds at
  most one value of the key; it needs a `str` or `str | None` field. A key without
  `single` may hold several values per entity, such as a person's emails. Ask
  whether a key is really single-valued: a person can have two ORCIDs.
- **Merging.** Records that share a value of any declared key are one entity,
  transitively. Values of different keys never meet: an ORCID never matches an
  email with the same text. Biotope compares values exactly; normalize them, such
  as case-folding emails, in the loader or mapping.
- **Natural key.** `natural="ensembl"` makes an entity whose records hold one value
  of that key take `ensembl:<value>` as its ID. The natural key must be one of the
  single-valued keys.
- **Derived IDs.** Any other entity gets `<concept>-<16 hex digits>`, a digest of
  its sorted record IDs, such as `reach:person-9f86d081884c7d65`. It is the same in
  every build while the entity keeps the same records, and changes when a record
  joins or leaves. Until B3 registers IDs, nothing outside the build should point
  at a derived ID.

## Contradictions

When a single-valued key would hold two values in one entity, biotope keeps apart
only the records, or the match links, that bridge those values, and the entities
the other records form without them stay as they are. The build goes on.

For example, a person formed from a roster row, a directory account and a profile
page, and another person formed the same way, each with its own roster record ID,
stay whole when a new roster row arrives whose email is the first person's and
whose ORCID is the second's. Only the new row is kept apart.

Biotope finds them in two steps, and no step depends on how records are named:

1. Records that hold a value of a single-valued key form groups through the values
   they share. While a group holds two values of a single-valued key, biotope
   keeps apart the record whose removal leaves the fewest contradictions; among
   equals, the one whose own values clash with more records it shares a value
   with, then the one that keeps more records together. Records that tie on all
   three are kept apart together.
1. The other records and the match links only join those groups. Where they would
   join two groups whose values contradict, biotope keeps apart the fewest of them
   that separate the two groups, links before records. When several such sets are
   equally small, it keeps apart those next to either group.

A record kept apart becomes an entity of its own with a derived ID and
`kept_apart: true`. A link kept apart is not applied.

## Match links

Fuzzy matching, such as on similar names, stays project code. A matcher is a
script the project runs before the build. It writes an ordinary input dataset of
SSSOM rows with an automatic justification, such as `semapv:LexicalMatching`, and
the project describes and loads it like any other source:

```text
# curie_map:
#   roster: https://example.org/roster/
#   directory: https://example.org/directory/
subject_id	predicate_id	object_id	mapping_justification	confidence
roster:recGrete0003	skos:exactMatch	directory:grete.hansen@example.org	semapv:LexicalMatching	0.889
```

A mapping turns each row into a `biotope.graph.Match`:

```python
def map_match(row: SourceRecord[Matches]) -> Iterator[Match]:
    link = row.value
    yield Match(
        concept=Person.schema_id,
        subject_id=link.subject_id,
        object_id=link.object_id,
        mapping_justification=link.mapping_justification,
        predicate_id=link.predicate_id,
    )
```

- `subject_id` and `object_id` name records of the concept by record ID or by a
  key value written `<key>:<value>`, such as `orcid:0000-0004-1234-5671`.
- The concept needs an identity declaration, and `predicate_id` must be
  `skos:exactMatch`.
- Biotope applies a link like a shared key value, the contradiction check
  included. A link that joins records no key had joined is an automatic merge: the
  entity lists it under `automatic` and the build's report under
  `automatic_merges`, and the link's row joins the entity's provenance.
- A link that names no record of its concept is listed under `unresolved_links`
  and changes nothing. A matcher that needs the current entities reads the
  previous build, so a record new in this build gets its links one build later.

The matcher judges equivalence, not biotope. In B3, a person's no-match decision
will override a link.

## Precedence declaration

`Precedence(concept, fields={...}, combine=(...))` says, for a node or relation
concept, which source wins for each field that several sources may fill.

- **Sources** are the `SourceContract` registrations the pipeline selects. A copy's
  source is the source whose loader read the records its mapping received:
  `context.load` marks each record with its source in `SourceRecord.sources`, and
  `context.apply` passes the marks on to its outputs. Evidence that two sources
  share does not change a copy's source. A copy that a mapping built from records
  of several sources ranks by the best placed of them.
- **First source wins.** For a field in `fields`, the entity takes the value of the
  first source in the list that has one; `None`, `""` and `[]` are no value. When
  two sources, or two records of one source, give different values, biotope lists
  a conflict and takes the value of the first source; within one source, the
  record with the lowest record ID, then the mapping name.
- **Combined lists.** A `list[str]` field in `combine` takes the items of every
  copy, each once, in a stable order: copies by their source's place in the
  field's list in `fields` (unlisted sources after), then by record ID; items in
  their order within each copy. It never conflicts.
- **No declaration.** When sources give different values for a field without a
  declaration, the build stops and names the entity, the field and each value with
  its source and record. When a field has a declaration but a source missing from
  its list gives a different value, the build stops in the same way. When all
  sources agree, or only one has a value, no declaration is needed.

## Relations

A mapping may give a relation's endpoint by any value that names an entity of the
endpoint's concept: a record ID, a key value written `<key>:<value>` or the
entity's ID. The endpoint's `NewType` still types it:

```python
Authored(source=PersonId(f"orcid:{row.orcid}"), target=PaperId(f"doi:{row.doi}"), position=row.position)
```

Biotope resolves each endpoint to the entity's ID. A reference that names no entity
stops the build. A reference that names several entities resolves to the one that
is not kept apart. A record kept apart answers to its own key values only where no
other entity holds them. When a reference still names several entities, because
only records kept apart hold its value, it resolves to none: the build leaves that
copy of the relation out, lists it under `ambiguous_endpoints` and goes on.

The copies of a relation that several sources give, identified by its type and
resolved endpoints, or by its `id` field when it has one, become one relation
with every copy's provenance. Two relations of different types with one `id` stop
the build. Precedence and the conflict list apply to a relation's fields as to an
entity's.

## What a build writes

`run.json`, and the JSON of `biotope graph quality`, hold an `identity` section:

- `entities`: per concept, the number of `entities`, of `records`, of entities
  `merged` from more than one record and of `derived_ids`; for a concept with an
  identity declaration, `merged_by_key` counts per key the merged entities in which
  that key's value joins two or more records. An entity joined by several keys
  counts under each; an entity joined only by a match link counts under none and
  is listed in `automatic_merges`.
- `contradictions`: per group, the `concept`, the single-valued `keys` with their
  values, the `entities` that stay whole and what was kept `apart`: each record
  with the ID of the entity it became, and each link.
- `conflicts`: the `concept`, the `entity` or the `relation` (its `source` and
  `target`, and `id` when it has one), the `field`, every `values` entry with its
  `source`, its `record` for an entity and its `value`, the `chosen` value and the
  `chosen_source`.
- `automatic_merges`: the `concept`, the `entity` and the link's `subject_id`,
  `object_id` and `mapping_justification`.
- `unresolved_links`: links that named no record, with what was `missing`.
- `ambiguous_endpoints`: relation copies left out because an endpoint names
  several entities: the relation's `concept`, the `relation` as the mapping gave
  it (`source` and `target`), which `endpoint`, the `entities` it names and the
  `sources` of the copies left out.

A build also writes the merged record of every entity to
`graph/build/entities.jsonl` and of every relation to `graph/build/relations.jsonl`:
one compact JSON object per line, sorted, with no timestamps, so two builds of the
same inputs give the same files.

- An entity line holds its `concept`, `id`, `records` with their `sources` and
  `mappings`, `keys` with their values and, in `fields`, the chosen value of each
  field. `from` names, per field, the records that give the chosen value, for the
  fields where not every record does; a field missing from `from` takes its value
  from every record, and a field without a value has no source. `derived: true`,
  `kept_apart: true` and the `automatic` links appear only when they apply.
- A relation line holds its `concept`, its `id` when the relation type has an `id`
  field, the resolved `source` and `target`, the `sources` of its copies and its
  `fields`, with `from` naming per field the sources that give the chosen value
  where not all do.

A value's source is read through the records `from` names, which carry their
sources, so no source is copied beside each value.

Every exported node and edge keeps the evidence of all its copies, and of its
automatic links, in `provenance.json`. The human output lists contradictions,
automatic merges and the first conflicts.

`biotope graph check` checks the declarations without reading data: every
identity names a node concept, its keys are `str` or `list[str]` fields, its
natural key is single-valued; every precedence names a concept, its fields are
properties, its sources are selected, and its combined fields are lists. The check
report lists the declarations under `identity` and `precedence`.
