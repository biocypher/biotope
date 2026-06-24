# Reliability principles

A knowledge graph's correctness is set mostly **before** the build — in how identifiers and data are prepared — not in the build or the query layer. These principles are durable; they hold regardless of biotope's version or any particular tool quirk. Most "the graph is missing answers" failures trace back to one of them.

## 1. Canonicalize identifiers up front, not after the fact

The single biggest lever on reliability is whether the same real-world entity gets the **same id everywhere**. When ids are canonical, BioCypher deduplicates nodes for free and you need no alignment step; when they aren't, edges whose endpoints don't match a node id are silently dropped and the graph quietly loses answers.

Do this before mapping:

- For each entity, pick **one id column that exists in every source** feeding it. If sources disagree (gene symbol vs Ensembl accession, `UBERON_0002107` vs `UBERON:0002107`, `UK` vs `United Kingdom`), normalize to one canonical form in a preprocessing step and carry the alternates as properties.
- Ground ids in an ontology/namespace where one exists (MONDO for disease, UBERON for tissue, EDAM for topics) so cross-source merges are principled, not coincidental.
- Make the preprocessing **idempotent** and keep it as a committed script — the canonicalization *is* the reusable artifact, more than the graph it produces.

The corollary: don't try to fix id mismatches downstream with alignment or hand-patches. Fix the namespace at the source.

## 2. Audit auto-proposed alignments; apply none blind

`propose-alignment` (and any automatic equivalence finder) keys off shared structure — a shared property name, a shared value. That heuristic happily proposes merges that destroy meaning: collapsing two *different* studies because they share `species: human`, or merging a gene with a transcription factor because they share a symbol. Each proposal carries a `reason` and `confidence` to inform your audit — read them, then apply only the equivalences that are true identity. When you've already canonicalized ids (principle 1), the correct alignment set is usually **empty** — and that's the healthy outcome, not a failure. Proposals are hypotheses, never instructions.

## 3. Verify the graph; never trust the build exit code

A build can succeed while dropping a large fraction of edges. After every build, check node and edge counts against what you expect (`biotope view`) and look specifically for **edge survival**: a relation that should carry thousands of edges but emits dozens is the signature of an id-namespace mismatch (back to principle 1), not a data shortage. Spot-check that the entities you care about actually carry the edges they should. Don't report a graph as working on the strength of a clean build alone.

## 4. Never fabricate data to satisfy a schema slot

If you declared a relation the data genuinely can't support, the honest move is to **surface the gap to the user** and defer the slot — `biotope map defer-relation <mapping> <relation>`, which `build` skips and counts honestly — not to satisfy the validator with an always-false filter, an empty mapping, or a placeholder. A graph that quietly lacks a relation it claims to have is worse than one that tells you the relation is unsupported. Validation passing is not the goal; a truthful graph is.

## 5. Keep the manifest and the data in sync

A mapping can only bind fields the manifest describes. When preprocessing adds or changes columns (a normalized key, a per-table ontology id), the manifest goes stale and the new column isn't mappable until you **re-describe the data**: `biotope add <dir> --rebake`. `map` warns when it detects this drift. (A single fixed constant doesn't need a column at all — use a `value:` literal in the mapping; see `mapping.md`. Reach for re-baking when the new value varies by row.)

## 6. Extraction from unstructured sources is the one genuinely manual step

Turning prose, PDFs, or free-text notes into structured rows is where real judgement lives — it can't be made fully deterministic. An agent can perform the extraction, but it must write the result as a **tracked, derived artifact** with an explicit provenance link to the source (`biotope add <derived> --derived-from <source>`), not smuggle the extracted facts straight into a mapping. This keeps the graph auditable and reproducible: a reader can see what was extracted, from what, and re-run it. Everything downstream of the extraction is mechanical and belongs to the deterministic `map → build` path.

## 7. One logical dataset → one manifest

Describe data at the granularity of the *dataset*, not the file. Pointing the tracker at individual partition files (or splitting one dataset across per-subdirectory adds) fragments lineage and breaks downstream scaffolding. Point `add` at the folder that *is* the dataset; give genuinely independent datasets their own manifests.

## 8. The declared schema is a contract — grow it, don't silently reshape it

Adding entities and relations is safe. Removing or restructuring what the user declared — or encoding a concept named in the `purpose` as something *other* than a first-class entity/relation — changes the meaning of the project and needs the user's explicit sign-off. Treat `required_entities` / `required_relations` and `purpose` as the user's words; resolve mappings *against* them rather than bending them to fit a convenient binding. The purpose sentence is what someone reading the project a year out will rely on.

---

**The through-line:** put the judgement early (canonical ids, honest schema, audited merges, careful extraction) and the mechanical build stays reliable. Effort spent making ids and the manifest correct up front is repaid many times over in answers the graph gets right.
