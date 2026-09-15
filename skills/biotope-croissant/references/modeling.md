# Preserving meaning while harmonizing

Harmonization should make sources comparable while preserving the distinctions needed to interpret them. Use the following examples to review modeling choices.

## Keep the observation separable from your reading of it

A source states what it measured. Anything you conclude from it is yours, and a consumer cannot tell the two apart once both are ordinary properties.

A rodent assay reports `mean_delta = -0.42` with the contrast written only as "treated vs. reference" in a figure legend you cannot recover. A `direction` property saying `decreased` then sorts, filters and compares exactly like a well-founded one.

A query ranking by direction may overlook a separate `direction_uncertain` flag. To preserve uncertainty, keep the raw effect and name the reference group in its description; attach `Interpretation(kind="uncertainty")` to that exact property; or do not publish the derived value. The same holds for any derived label — a severity band, a responder flag, a pathway assignment.

## Preserve the qualifiers that change what a claim means

Qualifiers determine how values can be compared. Units, reference group, timepoint, dose, assay platform, analysis population and covariate adjustment each change what a value asserts, and each is routinely dropped because the source kept it in a column name, a sheet title or a filename.

Two cohorts both report `hazard_ratio = 1.8`. One is adjusted for age and sex, the other unadjusted; one measures five-year survival, the other ten. Pooled into one concept with one property, their distinct interpretations are lost. Give the qualifiers their own properties or their own contrast node.

Where your name for something differs from the source's, keep the source's name too. A renamed column with no record of the original cannot be traced back.

## Two things a consumer must tell apart need a property that tells them apart

Similar labels from different studies are the easiest thing in a graph to conflate, and a consumer needs queryable context to distinguish them.

Two studies both report a "thrombus vs. control" comparison. One contrasts thrombus against matched peripheral blood; the other against healthy donors. Under one label they answer each other's questions silently.

Preserve the distinction in the export: the distinguishing value is queryable, an `Interpretation(kind="qualifier")` states how to choose between them, and a `QueryExample` selects one of them explicitly. A study or contrast node that exists but carries no distinguishing property does not count — it has to be the value a `WHERE` clause can filter on.

## Distinguish absence states

"Not significant", "not tested", "explicitly unassigned" and "not recorded" describe different states and should remain distinguishable.

A survey assigns each taxon to a community module; 2,000 rows carry the literal value `unassigned`. Dropping those rows makes deliberate non-membership indistinguishable from a taxon the survey never saw. Keep the explicit state as a value.

A differential table arrives pre-filtered by its authors. Naming its row count `features_tested` asserts a tested universe you do not have. Name it for what it is — rows supplied — and record the real coverage as unknown, or count it from a source that states it.

Nonsignificance is an observation about a threshold, not a statement that nothing happened. Do not describe it as "flat", "unchanged" or "no effect".

## Attach context-dependent relationships to what produced them

Some relationships hold only within the result that reported them. Detaching them merges evidence that was never pooled.

An enrichment analysis reports three results for one gene set, each from a different comparison, each with its own overlapping genes. An edge drawn directly from the gene set to each gene loses which result contributed it, and the term appears to overlap a union no analysis produced. Hang the overlap off the result node, or carry the result identity on the edge.

The same holds for an association reported only under one treatment arm, a correlation computed within one tissue, or a co-occurrence in one cohort.

## Keep study populations distinct from the concepts they resemble

Mapping a study's group onto an ontology term is a claim of equivalence. It is usually a claim of resemblance.

A trial's "elderly" arm is participants over 70 at one site. An ontology class for aged humans is broader and differently defined. Modeled as one node, every query touching the class inherits the trial's inclusion criteria. Keep the study-local population as its own node, relate it to the ontology term explicitly, and describe what that relationship does not assert.

Prefer a source-specific namespace wherever cross-source identity is unresolved. Merge only when source evidence supports shared identity.

## Resolve identity before anything depends on it

Identity resolution that runs while output is being emitted produces a graph whose contents depend on the order sources happened to be read.

A gene appears under a symbol in one table and an accession in another. If the first table's rows are emitted before the second establishes the accession, the gene becomes two nodes, and a later join across them finds nothing. The evidence was unambiguous; only the order was wrong. Gather identity evidence from every participating source in a first pass, resolve, then emit. Changing source order is a useful check that the result is independent of read order.

Keep unresolved identity visible. When sources disagree on which accession a symbol denotes, do not arbitrate silently and do not merge every symbol to make a join succeed. Keep the unresolved entity, record the candidates and what supports each, and relate the unresolved entity to them so a query reaches the evidence instead of dead-ending. Preserve every identifier and alias the sources supplied.

Then measure the joins you intended. For each cross-source join a capability depends on, report how much of it resolves, so readers can distinguish unresolved joins from absence in the sources.
