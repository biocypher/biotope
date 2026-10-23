# B3: Committed state

Needs: B2 · Roadmap decisions: 1, 8, 10–14 · Research: [`docs/research/b2-b3-state.md`](../research/b2-b3-state.md)

## Goal and why

After B3, a data product survives its rebuilds. An entity of a kind the project registers keeps an ID that never changes and is never reused. A person's decisions on matches, fields and links apply at every build under decision 11's rules. Every build is a release with a committed manifest and a diff against the previous release, built from input files checked against their Croissant descriptions.

Today `graph build` replaces its output, remembers no ID from one build to the next, and reads an input file that changed after it was described while `run.json` records the old hash (research note §1). REACH's Airtable rows and search point at person IDs, and Anna's corrections must hold through every rebuild. InTRAC needs to rebuild a past result and see what changed between two builds.

The milestone respects these roadmap decisions:

- 1 and 11: biotope applies decisions; interfaces for making them, such as REACH's Airtable tables and field sync, stay in the project.
- 8: the ID registry and the release manifests are committed and hold no personal values; decisions are an input dataset whose shape biotope defines, and each project chooses whether to commit it.
- 10: entities with natural keys keep them, and those without one get registered IDs with aliases and the date each was first seen. Since an entity can lack its kind's natural key, a project registers whole kinds, and a registered kind holds its natural key as an alias.
- 11: rejections stay rejected, decisions follow merged IDs, an override retires when the source agrees, a source change under an override is flagged, conflicting decisions are flagged and never ranked, and an invalid decision drops only itself and is reported.
- 12: a release records its inputs through Croissant's per-file sha256 and size, the build checks the files against them, and biotope stores no raw snapshots.
- 13 and 14: breaks get a `migration.md` note; tests use only public material.

## Scope

- The ID registry, one committed JSON Lines file that every build reads and extends.
- The decision dataset's shape, its validation, and its application during the build.
- An agent-facing command that records one decision in a project's committed decision dataset.
- Releases: a committed manifest per build, plain git over the manifests as history, and a diff between two releases by entity ID. Release data stays uncommitted and can be rebuilt.
- The input check: the build compares every file it reads with its manifest's sha256 and size, as `biotope check-data` does. When only the rows changed and the described fields are the same, the build refreshes the description, goes on, records the new sha256 and size in the release and flags the file there as refreshed; when the fields changed, it stops for review. `graph check` and `quality` report both without changing anything.
- The `biotope-croissant` skill: the agent records a decision only on a person's explicit word and reports a build through its diff.

## Non-goals

- Topology evolution (B4). B3 only needs IDs and decisions to survive a rebuild.
- Storing raw snapshots, and DVC, Dolt, lakeFS or git-annex: Croissant already hashes the files, and these tools add file-level tracking, binaries or servers without a record-level diff (research note §2).
- A history of retired overrides: biotope reports a retirement and the project removes the decision.
- Interfaces for making decisions, reading them from Airtable, field sync, the departure brake and anything else specific to REACH.
- Committing release data; diffs of the graph export or SQLite.

## Interfaces

**ID registry.** A committed JSON Lines file, sorted so its git diff stays readable. The project declares which kinds are registered and the pattern of each one's new IDs, such as `p-000123`; other kinds keep B2's IDs. A project may seed the registry with its existing IDs, their aliases and first-seen dates, and biotope keeps them as given. It promises:

- every entity of a registered kind has one ID; an issued ID never changes and never passes to another entity, even after the entity leaves every source;
- every key value that identified an entity under B2, natural keys and B1's record IDs included, is an alias with the date it was first seen, so an entity without its natural key keeps its ID when the key appears; an extracted record whose document moved keeps its entity, recognised by the document digest and key values that B1 stores, without B1's run report;
- when two entities merge, the older ID survives and the other stays as its alias, so anything pointing at it still resolves; when a no-match splits an entity, a part that had its own ID before a merge takes it back; of parts that held one ID, the part holding the record of the source the project ranks highest, such as rows people create, keeps it, ties break deterministically, and the other part gets a new ID;
- a key the project declares personal, such as an email, enters only as an opaque keyed hash; the registry holds no clear value of it, inside IDs included, and no decision.

**Decision dataset.** An input dataset like any other, described by Croissant and checked under decision 12. Each decision names its target by entity ID, alias or record ID, and carries its author, date and an optional comment.

- Match and no-match decisions are SSSOM TSV rows: `subject_id`, `predicate_id` `skos:exactMatch`, `object_id`, `mapping_justification` `semapv:ManualMappingCuration`, `predicate_modifier` `Not` for a no-match, `author_id`, `mapping_date` and `comment`. A match merges two entities and outranks a contradiction it causes on a single-valued key, which is reported, not enforced. A no-match keeps them apart even when declared keys or a matcher's automatic links join them; as for B2's contradictions, a record that shares a key with both parts stays apart and is listed.
- Overrides and link edits use one small format whose field names come from PROV-O and SSSOM. An override replaces one field's value, a list field's whole list included, and records its base, the source value it replaced. An override of a declared key adds its value to B2's identity; the value it replaced keeps identifying the entity until a no-match rejects that join. A link exclusion removes a relation, with every source's copy, or a list item the sources give; an added link adds one.

**Decision rules.** Each build applies decision 11: a no-match holds while the sources keep joining the pair; a decision on a merged-away ID applies to the surviving entity; an override whose source starts to send its value retires, and biotope reports it at each build until the project removes the decision; a source value that differs from both an override's base and its value keeps the override and flags it with all three; decisions that contradict each other on one target all stay unapplied and are listed; an invalid decision, such as one with an unknown target or field or a malformed row, is dropped alone and listed with its reason, and the build goes on.

**Recording a decision.** The command appends one decision to the project's decision dataset, fills its author, date and, for an override, its base from the current release, refreshes the dataset's Croissant description so the next build reads it, and refuses an invalid decision with its reason. Projects that collect decisions elsewhere write the dataset themselves.

**Release manifest.** Committed per build. It holds no record values, only entity IDs, counts and the names of fields and sources: the release's ID; each input manifest with every file's sha256 and size, and a flag on each file the build refreshed; digests of the registry and the decision dataset; the code digests `run.json` holds today; counts per entity kind; the entities, keys, fields and sources of B2's contradictions, conflicts and automatic merges; each decision's outcome (applied, retired, flagged, contradicted or dropped) by its target's entity ID; and the diff summary against the previous release, the one the previous committed manifest names, or a note that the diff is unavailable when that release's data is absent. The values behind these lists go to the build's uncommitted output.

**Diff.** Between two releases whose data is present, per entity kind and by entity ID: the entities added and removed, and for each changed entity the names of its changed fields.

## Acceptance criteria

Unit fixtures: invented people from three sources modelled on REACH's R7 scenarios (example.org emails, invented ORCIDs with valid checksums, made-up names), a few papers with and without DOIs and public genes, changed between builds.

- **AC-1** (unit) Over three builds whose sources reorder, add and drop people, from a registry seeded with `p-000123`-style IDs, aliases and first-seen dates, every entity keeps its ID, seeded ones included, new IDs follow the declared pattern, a person who left every source keeps theirs in the registry, no ID is issued twice, and each alias keeps its first-seen date. A build with nothing changed leaves the registry byte-identical. Emails declared personal appear nowhere in the registry in clear and still merge records across builds. A paper of a registered kind keeps its ID when its DOI first appears, and genes, a kind not registered, keep their Ensembl IDs.
- **AC-2** (unit) A key shared from the second build on merges two people: the older ID survives, the other resolves to it, and a decision written against the other ID applies to the survivor. A no-match then splits them, each part takes back its own ID, and the pair stays apart over three builds while the sources keep the shared key. A no-match that splits a person formed in one build, without any override, leaves the ID with the part holding the highest-ranked source's record, gives the other part a new ID, and makes the same choice for equal ranks in every build. A record that shares a key with both parts of a no-match stays apart and is listed. A no-match undoes a matcher's automatic link.
- **AC-3** (unit) An override over builds: set to X with base A while the source sends A, nothing is flagged; the source sends B, X stays and is flagged with A, B and X; the source sends X, the override is reported retired at each build until the decision is removed; the source then sends C, which applies without a flag. An override of a list field replaces the whole list, an excluded and an added list item hold while the source's list changes, and an override of an ORCID joins the person with the records carrying that ORCID, while the records carrying the replaced ORCID stay joined until a no-match rejects them.
- **AC-4** (unit) A match merges two people B2 kept apart, also when each holds its own single-valued record ID, and that contradiction is reported; a link exclusion and an added link hold over three builds while the sources keep giving the excluded link. A match and a no-match on one pair, and two overrides of one field with different values, all stay unapplied and are listed. An unknown target, an unknown field and a malformed SSSOM row are each dropped and listed with their reason while the other decisions apply.
- **AC-5** (unit) The record command appends a valid match, no-match and override with author, date and base, a build right after it runs and applies the decision, and it refuses an invalid one with its reason, leaving the dataset unchanged. A build that reads the decision dataset from an uncommitted file gives the same release as one that reads it committed.
- **AC-6** (unit) Each build writes a manifest with the contents the Interfaces list, and its diff against the previous release names the added, removed and changed entities with their changed fields; the diff between two earlier releases is the same when asked later. When the previous release's data is absent, the manifest records that the diff is unavailable and the build completes. The manifest holds none of the fixtures' emails or names, which the build's uncommitted output lists with the contradictions and conflicts. In a project made by `biotope init`, git tracks the registry and the manifests and ignores release data.
- **AC-7** (unit) After rows are added to an input file without describing it again, the build refreshes its description, runs, and the release records the new sha256 and size and flags that file as refreshed. After a column is added instead, `graph build` stops, names the file and the changed fields, and writes no release, and `graph check` reports the same; after the file is described again and reviewed, the build runs.
- **AC-8** (unit) Rebuilding at an earlier commit, with the input files and the previous release's data kept, reproduces that release's records and manifest, timestamps aside. Deleting every release and rebuilding, adding a concept and a field to the topology, renaming a mapping, and moving an extracted dataset's documents with `biotope mv`, then extracting again before the build, each keep every ID, alias and decision outcome.
- **AC-9** (manual) Vlad reads the `biotope-croissant` skill and confirms that the agent records a decision only on a person's explicit word, never on its own judgement, reports what a build changed from its diff, and follows the skill's ownership rule.

## Freedom to operate

The implementer decides everything the Interfaces leave open and documents in `docs/` what projects write or read: the registry's entry shape and default ID pattern, how kinds, patterns, source ranks and seeds are declared, the keyed hash and where its key lives, how a project names its decision dataset, the override and link-edit format beyond the named terms, release IDs, where uncommitted release data lives, the command's options, and whether a FileSet input is refused or its members' hashes are recorded.

## Design sketch (non-binding)

The research note's choices: about 60 lines for the registry, SSSOM read with the standard library and no sssom-py dependency, a join on ID per entity kind for the diff, and the `check-data` comparison called from `graph check` and `build`. A RecordSet's contract revision (`record_set_definition`) tells new rows from changed fields. The manifest can extend `run.json`.

## Risks and open questions

- A source whose described fields change, such as a fetched export that gains a column, stops the build until someone describes it again and reviews the change.
- A past release can be rebuilt only while the project keeps its input files; biotope cannot bring back what the project deleted.
- An override without a known base cannot be checked for source changes; the record command fills it, and projects that write decisions themselves must.

## Evidence required in the PR

- Unit test output, the `docs/` pages for the registry, the decision dataset, the command, the manifest and the diff, and the `migration.md` note.
- A sample committed manifest and diff from the test fixtures.
- For AC-9: Vlad's verdict.
- `uv run mkdocs build --strict` passing.
