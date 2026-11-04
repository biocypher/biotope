# Extraction

Extraction turns a project's documents, such as papers, saved web pages or
contracts, into structured records under a schema the user reviewed. Biotope
provides the interfaces, a scaffolded template and the runner; the project writes
one extractor per kind of document, with its own reading code, model calls and
keys. Each value keeps the quote or locator its extractor gave, and each record
names its document, schema revision and extractor. The records are registered as
an ordinary processed dataset, so `biotope source generate`, mappings and
`biotope graph build` read them like any other table. Graph checks and builds
never call an extractor.

## Workflow

```bash
biotope add data/papers
biotope extract try papers data/papers/smith2024.pdf
biotope extract run
biotope extract run papers --redo data/papers/smith2024.pdf
biotope source generate .biotope/datasets/data/extracted/papers.jsonl.jsonld --out graph/sources
```

- `biotope extract try NAME FILE...` runs one listed extraction on the given files
  and shows each record with its values and evidence. It changes nothing in the
  project, and the files need no dataset yet.
- `biotope extract run [NAME...]` runs the named extractions, or every listed one,
  stores each one's records in `data/extracted/<name>.jsonl` and registers that
  file as a dataset with status `processed`, derived from the datasets its
  documents belong to.
- `--redo FILE`, repeatable, extracts that document again although its inputs are
  unchanged. Its new records carry `"redone": true` in their provenance.
- Both take `--json` and then write one versioned JSON report to stdout. Both print
  `Extracting <n>/<total> <path>` to stderr, in document order, for each document
  they hand to an extractor.

## Declaring extractions

`graph/extraction/__init__.py` lists every extraction, as `topology/__init__.py`
lists the graph's classes:

```python
from biotope.extraction import Extraction

from .papers import Paper, PaperReader


EXTRACTIONS: tuple[Extraction, ...] = (
    Extraction(
        name="papers",
        schema=Paper,
        extractor=PaperReader,
        files=("data/papers/*.pdf", "data/papers/*.txt"),
        parallel=2,
    ),
)
```

- `name`: lowercase letters, digits and underscores. It names the records file,
  `data/extracted/<name>.jsonl`, and the run state.
- `files`: path patterns relative to the project root, as `pathlib` globs them,
  such as `pages/*.html` or `inbox/contract_*.pdf`. They decide which documents the
  extraction reads, so files of one kind can be routed by folder or name rather than
  by suffix. Hidden files and annotation files are never matched. Every matched file
  must be described by a dataset: `biotope add` it first, or the run fails and names
  it. `add` leaves out a file identical to another file of its dataset, so narrow
  the patterns to skip such copies. A pattern that matches no file fails the run.
  The records always mirror the files the patterns match now, so a new file joins
  on the next run and a removed one loses its records.
- `parallel`: how many documents the runner hands to the extractor at once, from
  separate threads; 1 by default.

Biotope imports the list through the graph workspace, as `graph check` and
`graph build` do, so extraction code can import other project modules, and the
scaffold lists `extraction` in the pipeline's `code_paths`, so `graph check`
type-checks it and `run.json` records it. Loading checks every entry: a schema
biotope cannot use, an extractor without a `name` or `version`, a pattern outside
the project or a repeated name fails before any document is read.

`biotope graph scaffold` writes the empty list and `graph/extraction/template.py`,
a bare schema and extractor whose first line, `# biotope:placeholder`, marks them
unfilled. Copy it for each kind of document. `graph check`, `extract try` and
`extract run` refuse a listed extraction whose schema or extractor file still has
that line, `graph check` as `extraction.placeholder`; an unlisted template is
ignored.

## Schemas

A schema is a dataclass. Its docstring says what kind of record a document states;
each field's `description` metadata says what to fill and becomes the field's
description in the registered dataset.

```python
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class FundingRound:
    """One funding round of a call for proposals."""

    __record_key__: ClassVar[tuple[str, ...]] = ("round",)

    round: str | None = field(metadata={"description": "The round's name as the call gives it."})
    deadline: str | None = field(metadata={"description": "The round's submission deadline, as written."})
```

A field's type is `str`, `int`, `float`, `bool` or a `Literal` of one of them,
optionally `| None`, or a list of one of them. Biotope refuses any other type, and
a schema without fields, naming the problem.

**Record key.** `__record_key__` names the fields that tell a document's records
apart. A schema without one yields at most one record per document. Two records of
one document with equal key values fail that document.

**Revision.** The SHA-256 digest of the schema's name, docstring, record key and
fields with their types and descriptions. Each record stores the revision it was
extracted under.

## Extractors

An extractor subclasses `biotope.extraction.Extractor`:

```python
from typing import Any

from biotope.extraction import Document, ExtractionError, Extractor, Schema


class PaperReader(Extractor):
    name = "paper-reader"
    version = "1"
    settings = {"model": "a-model-id"}

    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]:
        ...
```

- `name`, `version` and `settings` are class attributes, so biotope knows them
  without creating the extractor. Change `version` whenever the extractor's
  behaviour changes. `settings` holds the JSON values that shape its output, such as
  the model, never a key. All three go into every record's provenance, and a change
  to any of them extracts every document again.
- Biotope creates the extractor with no arguments, once per run and only when a
  document needs extraction, so a run that reuses every record needs no key. An
  extractor that cannot start, for example without its key, raises
  `ExtractionError` from `__init__`, and each document it would have read fails with
  that reason.
- `extract` gets a `Document` with the file's `path` and `sha256`, and the parsed
  `Schema`, with `name`, `description`, `key` and `fields`. It reads the file as the
  project needs: biotope converts no document.
- It returns the document's records. Each maps every schema field to
  `{"value": ..., "quote": "..."}` or `{"value": ..., "locator": "..."}`, and a list
  field to a list of such objects. A quote is text copied from the document; a
  locator is the extractor's own notation, such as `page 3` or `row 14`. A value
  without either has no evidence.
- It raises `ExtractionError` with a reason when a document cannot be extracted.
- With `parallel` above 1, `extract` runs in several threads at once. Guard a
  library that is not thread-safe, such as `pypdfium2`, with a lock.

Biotope validates every record against the schema. It does not check that a quote
occurs in the document or that a value is right: reviewing records is the agent's
and the user's work.

## Stored output

Each run writes `data/extracted/<name>.jsonl`, one record per line, sorted by ID.
Commit it; the `.gitignore` that `biotope init` writes keeps `data/extracted/` in
git.

```json
{
  "id": "calls/call.md#round=\"Full proposal\"",
  "document": "data/calls/call.md",
  "values": {
    "deadline": {"value": "30 April 2027", "evidence": {"quote": "| Full proposal | 30 April 2027 |", "locator": null}}
  },
  "provenance": {
    "document_sha256": "0e2faf46…",
    "schema": "FundingRound",
    "schema_revision": "065fb9fb…",
    "extractor": {"name": "round-reader", "version": "1", "settings": {}}
  }
}
```

- **ID.** The name of the document's dataset folder and the document's path within
  it, such as `pages/lind.html`, or the file name for a single-file dataset, then
  `#` and each key field as `name=<JSON value>`, joined by `;`. A value is
  written as the schema types it, so `1` and `1.0` of a `float` field are one key.
  Moving a dataset to another folder keeps its records' IDs. Documents of two
  datasets with the same name and path would share an ID, so the run refuses them.
- **Document.** The document's path from the project root.
- **Evidence.** The extractor's `quote` and `locator`, or `null` when it gave
  neither.

**Registered dataset.** The records file is registered at
`.biotope/datasets/data/extracted/<name>.jsonl.jsonld`, with status `processed`,
`prov:wasDerivedFrom` the datasets of its documents and a RecordSet keyed by `id`,
whose fields biotope writes from the schema, so `biotope source generate` produces
typed, nested record classes. It has no `creator` or `license` unless its annotation
file, `data/extracted/<name>.jsonl.biotope.yaml`, gives them. A folder dataset that
holds the records file, as `biotope add data` holds `data/extracted/`, leaves the
file out. `biotope source generate` writes no source package for a document that an
extraction has read, since its records are mapped instead, and reports a package
generated for it before the run as orphaned: delete that package.

To remove an extraction, delete it from the list and run
`biotope rm data/extracted/<name>.jsonl`, which also removes its run state, so
generation gives its documents packages again. To rename an extraction, rename it,
run it and remove the old records file the same way.

**Run state.** `.biotope/extraction/<name>.json` records the files the extraction
matched and, per document, the digest, schema revision and extractor that produced
its stored records. Commit it. Each document's records are kept in
`.biotope/progress/` as soon as it is extracted; the records file and the run state
are written only when the run completes, so an interrupted run changes neither and
the next run reuses what it finished. `biotope mv` refuses to move a records file:
rename the extraction instead.

## Reuse and the report

A document is extracted again only when its digest, the schema revision, or the
extractor's name, version or settings change. Otherwise its stored records are
reused, also after `biotope mv` moved it. A document that fails keeps its stored
records. The report lists, per extraction, each document as `extracted`, `empty`
(no record), `reused` or `failed` with its reason; the record IDs that disappeared
and appeared; each moved ID with its new one; and the output files git ignores. The
run exits nonzero when a document failed.
