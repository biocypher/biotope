# Annotating datasets

## Everything people write goes into the annotation file

Each dataset has one annotation file next to its data: `<folder>/.biotope.yaml` for a folder added with `biotope add <folder>`, `<file>.biotope.yaml` for a single file. `biotope add` creates it with a header comment and no values. The manifest in `.biotope/datasets/` is the data, as Baker describes it, with this file over it: never edit the manifest, and never copy, edit and register it.

The file is sparse. A value there wins over the data's, a missing value comes from the data, and an empty value clears what the data says:

```yaml
# What people write about this dataset. A value here wins over the data's; an empty value clears it.
description: Differential expression in atrial fibrillation from two studies, with their methods note.
license:  # the README states no licence; asked the user on 2026-10-27
tables:
  study_a.csv#study_a:
    description: One row per gene in study A.
    key: gene
    columns:
      padj:
        description: Benjamini-Hochberg adjusted p-value; empty when the gene was filtered before testing.
      ensembl_id:
        description: Ensembl gene accession, as the study reports it.
        equivalentProperty: https://schema.org/identifier
```

- Top-level keys are dataset fields, written into the manifest as Croissant keys: `name`, `description`, `license`, `creator`, `citeAs`, `keywords`, `url`, `version` and the like. A `creator` given as a name or a mapping becomes a `Person`.
- `tables` is keyed by table ID, as `biotope map inspect <manifest> --json` prints it. A table takes a `description`, a `key` (a column name or a list of them) and other Croissant keys; `columns` is keyed by each column's name in the data and takes a `description`, an `equivalentProperty` and other Croissant keys.
- `file_sets` renames a file set, keyed by its include pattern, which also renames its ID: `file_sets: {events/*.parquet: events}`.
- Column types and nullability belong in each source's `schema.py`, not here.

Write values by hand or with commands, which write only the values given and keep comments:

```bash
biotope annotate set data description="Differential expression in atrial fibrillation from two studies."
biotope annotate set data --table 'study_a.csv#study_a' --column padj description="Adjusted p-value; empty when untested."
```

Without `--table`, `annotate set` writes dataset fields; with `--table` a table's, named by its ID with or without percent-encoding, such as `'x - y.csv#x - y'`; with `--column` a column's. A repeated key makes a list, and an empty value clears. It refuses a table or column the manifest does not have. On the first `biotope add`, or with `--rebake`, flags such as `--description`, `--license`, `--creator` and `--citation` write dataset fields into the same file.

Name the evidence for each value, and any unresolved gap, in a YAML comment beside it, so a later reviewer can assess it. Comments survive every command.

## A hand edit takes effect on the next read, and a rebake keeps it

Every command that reads a manifest applies the annotation file's current content, so an edit reaches `biotope graph check`, `graph build`, `source generate` and `map inspect` with no other step. `biotope add --rebake <path>` describes the data again and applies the file again; it always succeeds and never changes the annotation file. When the file names a table or column the data no longer has, `add` warns and names it: fix or remove that entry.

Descriptions and equivalent properties change no revision. A key is structure: declaring, changing or removing one changes the source's revision once, and `graph check` reports `source.drift` until the schema's `__source_digest__` is updated ("When the data changes" in SKILL.md).

## Documents are sources too

A file Baker cannot parse can still answer a semantic question. Cohort descriptions, methods sections and supplementary notes routinely carry the reference group, the inclusion criteria or the units that the tables leave implicit.

`biotope add <dir>` reports such files as `unclaimed` and still gives each a file entry whose ID is its path in the dataset:

```json
{
  "@type": "cr:FileObject",
  "@id": "methods.txt",
  "name": "methods.txt",
  "contentUrl": "methods.txt",
  "encodingFormat": "text/plain",
  "sha256": "38bc5683…",
  "contentSize": "506"
}
```

Keep these entries. Extract the records a document holds with `biotope extract`, as [extraction.md](./extraction.md) describes; the extracted records become a dataset of their own. Generation still gives each document a document package: exclude it with the reason `extracted into <records file>`, or, for a document the user kept out of extraction, use its `Facts` schema for what you transcribe, with a loader that cites the page or section of each statement.

The ID follows the path, never the content, so a re-downloaded document keeps its ID and its package. A changed document is extracted again on the next `extract run`. Transcribed facts are not re-read automatically: `biotope check-data` reports the changed file, and you check the facts against it.

A file outside every added folder is described by adding it, `biotope add <file>`, never by a FileObject written by hand.

`biotope add` registers byte-identical files once and names each copy it skipped. A file the dataset's description already holds stays registered; otherwise the first path in sorted order does. Baker never parses a copy, and a FileSet whose pattern covers one lists it under `excludes`.

Whether a file can be ingested and whether it should be read are separate questions. A described file that the graph does not need is excluded with a reason in `graph/sources/__init__.py`, not removed from the manifest.

## Structured files Baker cannot parse

Baker has no handler for some structured formats, such as tab-separated `.txt`, RDF (N-Triples, N-Quads, Turtle) and shapefiles, so `biotope add` reports them `unclaimed`. A RecordSet written by hand has no home: the annotation file describes only structure the data has, and the next rebake would drop it. The file's own package reads it instead:

- In its `schema.py`, declare one field per value the loader decodes under the generated `Facts` class: each column of a table; the subject, predicate, object and graph of a statement; the attributes and geometry of a feature. Rename the class if `Facts` misleads.
- The loader parses the file at `SOURCE.path()` with an established library and yields one record per row, statement or feature, citing its line or feature number as the location.
- A companion file that only the loader of another source reads, such as a shapefile's `.shx` index, keeps its own package: exclude it with a reason that names the source whose loader reads it.

When the project itself writes the file, writing it in a format Baker parses, such as `.tsv` or `.csv`, gives it tables and fields in the manifest instead. That choice is the project's.

## Keep structural gaps visible

Validate fields, types and physical access against the source before relying on them in a mapping. Keep unsupported inputs, partial manifests and opaque fields visible instead. An opaque field that nothing reads can stay `None`; one a requirement needs gets a concrete type in its schema and a loader that decodes it.
