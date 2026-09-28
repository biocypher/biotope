# Correcting and registering manifests

## A correction is a separate file, registered with its evidence

Copy the manifest into `.biotope/reviews/` and correct the copy, never inside the graph workspace. Never edit a manifest in `.biotope/datasets/` directly. Register the draft with the evidence that justifies it:

```bash
biotope source register <file> --name <managed-name> --reason "<evidence and gaps>"
```

Name the evidence reviewed and any unresolved gaps so a later reviewer can assess the correction.

## `--replace` overwrites without merging

Compare the draft against the current manifest first, including its curation notes. The command reports removed structure, then replaces the file — it does not merge, and it does not pause. Changed values need the same review as removed ones.

## Refresh curated metadata separately

Once a manifest is curated or annotated, `biotope add` will not overwrite it. To see what a fresh bake would produce, direct it elsewhere:

```bash
biotope add <data-path> --bake-to <new-review-file.jsonld>
```

Put that file in `.biotope/reviews/`, outside both the input directory and `.biotope/datasets/`. Reconcile the two by hand, keeping reviewed corrections and annotations.

## Generate from the manifest, never from a draft

`biotope source generate` takes the registered `.biotope/datasets/<name>.jsonld`. A draft under `.biotope/reviews/` has not been reviewed and is not the contract the project builds against. A registration that changes a source's contract changes its revision, so run `biotope source generate` and `biotope graph check` afterwards and follow "When a manifest changes" in SKILL.md for any `source.drift`.

## Documents are sources too

A file Baker cannot parse can still answer a semantic question. Cohort descriptions, methods sections and supplementary notes routinely carry the reference group, the inclusion criteria or the units that the tables leave implicit.

`biotope add <dir>` reports such files as `unclaimed` and still appends a FileObject for each one to the manifest:

```json
{
  "@type": "cr:FileObject",
  "@id": "file_9e20cb96",
  "name": "methods.txt",
  "contentUrl": "data/methods.txt",
  "encodingFormat": "text/plain",
  "sha256": "9e20cb96…",
  "contentSize": "62"
}
```

Keep these entries. Generation gives each one a document package whose `Facts` schema holds what you transcribe, and whose loader cites the page or section of each statement. The `@id` follows the file's checksum, so the reviewed facts stay bound to the exact content they describe. A replaced document gets a new `@id`, leaving the old package orphaned; the orphan finding names the new resource so you can move the reviewed facts across.

Add a FileObject by hand only for a file that no scan covered, in a draft registered as above. Give it a stable `@id`, its `contentUrl` relative to the project root (as in the entries `biotope add` appends; Baker's own entries are relative to the directory it scanned), `encodingFormat` and `sha256`.

`biotope add` registers byte-identical files once, under the first path in sorted order, whether Baker parses them or not, and names each copy it skipped. Members of one FileSet, such as identical images in a collection, all stay.

Whether a file can be ingested and whether it should be read are separate questions. A described file that the graph does not need is excluded with a reason in `graph/sources/__init__.py`, not removed from the manifest.

## Structured files Baker cannot parse

Baker has no handler for some structured formats, such as tab-separated `.txt`, RDF (N-Triples, N-Quads, Turtle) and shapefiles, so `biotope add` reports them `unclaimed`. When the graph reads records from such a file, describe them as a RecordSet over the FileObject that `biotope add` appended, rather than transcribing them as a document. Every field names that FileObject as its source:

```json
{
  "@type": "cr:RecordSet",
  "@id": "places",
  "name": "places",
  "field": [
    {
      "@type": "cr:Field",
      "@id": "places/place_id",
      "name": "place_id",
      "dataType": "sc:Integer",
      "source": { "fileObject": { "@id": "file_66121526" }, "extract": { "column": "place_id" } }
    }
  ]
}
```

- A field's `@id` is `<record set @id>/<field>`.
- Declare one field per value the loader decodes: each column of a table; the subject, predicate, object and graph of a statement, extracted from `{"fileProperty": "lines"}`; the attributes and geometry of a feature.
- A file that a field reads gets a record-set package instead of a document package. A file that no field reads, such as a shapefile's `.shx` index, stays a document source: exclude it with a reason that names the source whose loader reads it.
- The loader parses the file with an established library and yields one record per row, statement or feature.

Keep document sources for prose whose facts you transcribe, such as methods, cohort descriptions and notes. Register the corrected draft as above, then generate.

## Keep structural gaps visible

Validate fields, types and physical access against the source before relying on them in a mapping. Keep unsupported inputs, partial manifests and opaque fields visible instead. An opaque field that nothing reads can stay `None`; one a requirement needs gets its metadata refined first. Keep every field `@id` scoped under its RecordSet (`<record set @id>/<field>`), as Baker and `biotope annotate` write them; other ids cannot be bound by generated schemas and are reported as `source.unscoped_field`.
