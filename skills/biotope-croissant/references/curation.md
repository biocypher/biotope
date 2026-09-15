# Correcting a source description

## A correction is a separate file, registered with its evidence

Write the corrected description under `graph/metadata/` when a graph workspace exists, or `.biotope/reviews/` for metadata-only work. Never edit a managed description in `.biotope/datasets/` directly. Register it with the evidence that justifies it:

```bash
biotope source register <file> --name <managed-name> --reason "<evidence and gaps>"
```

The reason is read by whoever revisits the decision. "Corrected field type" says nothing; name what you read and what remains unresolved.

## `--replace` overwrites without merging

Compare against the current managed description first, including its curation notes. The command reports removed structure, then replaces the file — it does not merge, and it does not pause. Changed values need the same review as removed ones.

## Curation protection blocks rebaking, and should

Once a description is curated or annotated, `biotope add` will not overwrite it. To see what a fresh bake would produce, direct it elsewhere:

```bash
biotope add <data-path> --bake-to <new-review-file.jsonld>
```

Put that file in the review location above, outside both the input directory and `.biotope/datasets/`. Reconcile the two by hand. Removing the protection to make a rebake succeed discards the curation it exists to defend.

## Generate from the managed description, never from a draft

`biotope source generate` takes the registered `.biotope/datasets/<name>.jsonld`. A draft under `graph/metadata/` has not been reviewed and is not the contract the project builds against.

## Missing ingestion support is not missing evidence

A file Baker cannot parse can still answer a semantic question. Cohort descriptions, methods sections and supplementary notes routinely carry the reference group, the inclusion criteria or the units that the tables leave implicit. Read them when a capability depends on something the data does not state, and record what you learned as a property description or an `Interpretation` naming its source.

Whether a file can be ingested and whether it should be read are separate questions.

## Never invent structure to make a mapping work

An invented field, a guessed type or a loader inferred from metadata all produce a project that type-checks and is wrong. Keep unsupported inputs, partial descriptions and opaque fields visible instead. An opaque field that nothing reads can stay `None`; one a capability needs gets its metadata refined first.
