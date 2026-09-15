# Correcting a source description

## A correction is a separate file, registered with its evidence

Write the corrected description under `graph/metadata/` when a graph workspace exists, or `.biotope/reviews/` for metadata-only work. Never edit a managed description in `.biotope/datasets/` directly. Register it with the evidence that justifies it:

```bash
biotope source register <file> --name <managed-name> --reason "<evidence and gaps>"
```

Name the evidence reviewed and any unresolved gaps so a later reviewer can assess the correction.

## `--replace` overwrites without merging

Compare against the current managed description first, including its curation notes. The command reports removed structure, then replaces the file — it does not merge, and it does not pause. Changed values need the same review as removed ones.

## Refresh curated metadata separately

Once a description is curated or annotated, `biotope add` will not overwrite it. To see what a fresh bake would produce, direct it elsewhere:

```bash
biotope add <data-path> --bake-to <new-review-file.jsonld>
```

Put that file in the review location above, outside both the input directory and `.biotope/datasets/`. Reconcile the two by hand. Retain reviewed corrections and annotations when reconciling a fresh description.

## Generate from the managed description, never from a draft

`biotope source generate` takes the registered `.biotope/datasets/<name>.jsonld`. A draft under `graph/metadata/` has not been reviewed and is not the contract the project builds against.

## Read supporting evidence

A file Baker cannot parse can still answer a semantic question. Cohort descriptions, methods sections and supplementary notes routinely carry the reference group, the inclusion criteria or the units that the tables leave implicit. Read them when a capability depends on something the data does not state, and record what you learned as a property description or an `Interpretation` naming its source.

Whether a file can be ingested and whether it should be read are separate questions.

## Keep structural gaps visible

Validate fields, types and physical access against the source before relying on them in a mapping. Keep unsupported inputs, partial descriptions and opaque fields visible instead. An opaque field that nothing reads can stay `None`; one a capability needs gets its metadata refined first.
