# Sidenotes

Not part of the workflow. Nothing in `SKILL.md` or `references/` requires this
file, and it is deliberately unlinked so it costs an executing agent nothing.
It holds material that was true and useful but did not change what the agent
does, kept for whoever maintains the skill.

## Diagram labels

A node or relation may declare `display_name: ClassVar[str]` beside its
`schema_id` for a short label in the metagraph viewer — "Sample", "Measured in".
The fallback is the Python class name split into words. Labels do not change
identity, exported data or the topology digest.

## The reserved namespace

Concept IDs in the `biotope:` namespace are rejected. Biotope uses it for the
export metadata rows that carry the interpretation context into a database, and
the reservation keeps a project concept from colliding with them.

## Regeneration freshness

`biotope source generate ... --check` reports each source package's freshness
without creating files. A record set removed from a manifest leaves an orphaned
package, which is reported and never deleted; removing it is a project decision.

## Run fingerprints and digests

Run records use metadata fingerprints and project-supplied versions rather than
a second full-data hash pass. `graph_digest` compares graph content across runs
without timestamps or paths, which helps review repeated deterministic runs. It
does not prove an arbitrary pipeline reproducible, and it does not justify extra
full-data runs. Biotope's own source digest identifies local edits that a
package version cannot.

## Provenance attribution

Each output receives the inputs of the mapping call that produced it, including
both sides of a join, so a sample produced by a sample-and-person mapping also
references the person row. That is not evidence that every input determined
every property. Use smaller mappings where narrower attribution matters.
Aggregates may reference a project-maintained contributor artifact; Biotope
infers no field-level lineage.

## Memory

The engine retains graph objects, identities and evidence in memory for
deduplication and endpoint checks, and project joins may retain more. There is
no disk-backed state engine, so feasibility is a property of the agreed scope.

## Queue states

Biotope's status, annotation and tracking commands remain available alongside
graph work. Queue states describe metadata workflow and certify nothing about
graph validity. Use ordinary Git to version authored Python alongside metadata.

## Retired guidance

Earlier versions of Biotope drove graph construction from YAML mappings and an
interactive wizard. Both are gone; Python definitions are the only authority. A
project still carrying YAML mapping files needs migration, not reconciliation.
