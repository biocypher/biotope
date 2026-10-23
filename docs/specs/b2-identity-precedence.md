# B2: Identity and precedence

Needs: B1 · Roadmap decisions: 1, 7–10, 13, 14 · Research: [`docs/research/b2-b3-state.md`](../research/b2-b3-state.md)

## Goal and why

After B2, a project declares which keys identify each kind of entity and which source wins for each field. Biotope merges the records that share a declared key into one entity, takes each field from the first source in the declared order, and lists every contradiction and field conflict it found in the build's output.

Today two graph objects with one ID and different values stop the build, and a project resolves identity and conflicts in Python inside its mappings; the `alignment/` package that `graph scaffold` writes is empty. A reviewer cannot see which keys merge what, or which source wins. REACH merges people from several sources on ORCID, email and record IDs, and InTRAC merges genes across studies by Ensembl ID. Both need these rules as artefacts a person can review. B2 stores nothing: registered IDs and human decisions come in B3.

The milestone respects these roadmap decisions:

- 1: biotope is not a judge of equivalence; it merges only on keys the project declared.
- 7: an agent proposes the declarations from the project's purpose and a person reviews them; the agent stops and asks before merging identities without a shared accession.
- 8: a build stays a pure function of its inputs and the project's committed files.
- 9: identity and precedence are explicit, reviewable artefacts, and matching rules stay project code.
- 10: entities with natural keys, such as genes and DOIs, keep them as their IDs.
- 13 and 14: 0.10's conflict behaviour may break, with a note in `migration.md`; tests use only public material.

## Scope

- An identity declaration and a precedence declaration per entity kind, written in the project's graph code next to the topology.
- Merging of records that share a value of a declared key, transitively, with networkx's `UnionFind` (already installed through mlcroissant), and a contradiction check on each merged group.
- Proposals from project matchers, listed and never merged.
- Field precedence applied by biotope, with conflicts listed.
- Entities, contradictions, conflicts and proposals in the check, quality and build reports and in `run.json`.
- The `biotope-croissant` skill: the agent proposes both declarations from the project's purpose and sample records and shows the user the merges, contradictions and conflicts before they are adopted.

## Non-goals

- Registered IDs, aliases with dates, match and no-match decisions, overrides and link edits (B3). B2 writes no file that a later build reads.
- Fuzzy or probabilistic matching in biotope, such as name similarity or scoring, and linkage libraries such as splink, recordlinkage or dedupe.
- Normalizing key values, such as case-folding emails or checking ORCID checksums; projects do it in their loaders or mappings.
- Topology changes (B4) and REACH-specific rules, such as Airtable rows or the departure brake.

## Interfaces

**Identity declaration.** For each entity kind, the project names the keys that identify its records: natural keys such as an Ensembl ID or a DOI, aliases such as an email or an ORCID, a source's own record IDs and B1's extracted record IDs. Each key is single-valued or multi-valued per entity. Values of different keys never meet, so an ORCID never matches an email with the same text. A kind may name one natural key whose value becomes the entity's ID. Records that share a value of any declared key are one entity, transitively. An entity of a kind without a natural key gets an ID derived deterministically from its records; B3 replaces it with a registered ID.

**Contradiction.** A group in which a single-valued key holds two different values merges none of its records. Biotope lists the group, the key, its values and the records, and the build goes on. For example, a record whose email is one person's and whose ORCID is another's, when each person carries its own value of a single-valued record ID.

**Proposal.** A matcher is project code that receives the entities of a kind and returns proposed pairs, each with its rule and evidence. Biotope lists each proposal with both sides and merges nothing because of it. In B3, a person's confirmation or rejection of a proposal becomes a match or no-match decision.

**Precedence declaration.** For each field that several sources may fill, the project gives an ordered list of sources, and the entity takes the value of the first source that has one. A list field may instead combine the values of all sources, deduplicated in a stable order. When two sources, or two records of one source, give different values, biotope lists a conflict and chooses deterministically. When sources disagree on a field without a declaration, the build stops and names the entity, the field and the values, as today.

**What later stages read.** One merged record per entity, with its ID, the records that formed it, its key values and, per field, the chosen value and its source. Exported objects keep the provenance of every member record. The build's output lists the contradictions, the conflicts (entity, field, each source's value and the chosen one) and the proposals; B3 copies these lists into the release manifest.

## Acceptance criteria

Unit fixtures: two small gene tables shaped like InTRAC's studies, with public Ensembl IDs and one gene whose symbol differs between them, and invented people from three sources modelled on REACH's R7 scenarios (example.org emails, invented ORCIDs with valid checksums, made-up names).

- **AC-1** (unit) Genes of the two studies that share an Ensembl ID become one entity whose ID is that Ensembl ID, with both studies' records as members. The gene whose symbol differs takes the symbol of the first source in the declared order, and the conflict lists both values, their sources and the chosen one. Reversing the order changes only that choice.
- **AC-2** (unit) People records from three sources merge transitively on shared emails, ORCIDs and record IDs. Shuffling the sources and their records gives identical entities, IDs, members, chosen values and lists. A second build after deleting the first one's output gives the same result.
- **AC-3** (unit) A record whose email matches one person and whose ORCID matches another, each with its own single-valued record ID, merges nothing: every record of that group stays apart, the contradiction lists the group, the key, its values and the records, and the build completes.
- **AC-4** (unit) A record of a B1 extracted dataset joins an entity through a declared key, such as an ORCID quoted on a profile page, and the merged entity's provenance names the document and the evidence alongside the structured records.
- **AC-5** (unit) A matcher outside the `biotope` package that proposes pairs by similar names has each proposal listed with both sides, its rule and its evidence, and no entity merges because of it.
- **AC-6** (unit) A combined list field holds every source's values once, in a stable order. Sources that disagree on a field without a declaration stop the build with a message naming the entity, the field and the values.
- **AC-7** (manual) Vlad reads the `biotope-croissant` skill and confirms that the agent proposes both declarations from the project's purpose, shows the merges, contradictions and conflicts before adopting them, and stops to ask before any merge without a shared key. With declarations an agent proposed and Vlad approved, a build of the InTRAC project at `/home/vladsam42/Projects/biotope_project/scratch/intrac_test/` merges genes of at least two studies by Ensembl ID, and Vlad judges its conflict list.

## Freedom to operate

The implementer decides everything the Interfaces leave open and documents in `docs/` what projects write: how the declarations are written (topology metadata, the `alignment/` package or both), how mappings receive merged records, where in the pipeline merging runs, how an ID is derived for a kind without a natural key, the tie-break within one source, the matcher's signature and the reports' format.

## Design sketch (non-binding)

Union-find over records keyed by (key name, value), then a check per group for single-valued keys with several values, as in the research note §4. `graph check` can verify statically that every declared key and source exists.

## Risks and open questions

- Until B3, an entity without a natural key may change ID when its group changes, so nothing outside the build should point at those IDs yet.
- A key declared single-valued can be too strict for real data, such as a person with two ORCIDs; the declaration makes it multi-valued, and the skill should ask.
- networkx arrives only through mlcroissant; biotope should declare it directly.

## Evidence required in the PR

- Unit test output, the `docs/` pages for both declarations and the matcher, and the `migration.md` note.
- For AC-7: the approved declarations, the InTRAC build's conflict list and Vlad's verdict.
- `uv run mkdocs build --strict` passing.
