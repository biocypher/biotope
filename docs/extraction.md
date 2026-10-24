# Extraction

Extraction turns local documents, such as PDF papers, saved HTML pages and text
files, into structured records under an extraction schema that a person
reviewed. Every value carries its evidence, and every record names its document,
the schema revision and the extractor that produced it. The records are stored in
the project and registered as an ordinary processed dataset, so
`biotope source generate`, mappings and `biotope graph build` read them like any
other structured file. Graph checks and builds never call an extractor.

Documents must already be registered with `biotope add`. Biotope never downloads
them. Send only public documents to an external model.

## Workflow

```bash
biotope add data/pages
biotope extract schema extraction/schemas.py:Profile
biotope extract try extraction/schemas.py:Profile data/pages/lind.html
biotope extract text data/pages/lind.html
biotope extract run extraction/schemas.py:Profile data/pages
biotope extract run extraction/schemas.py:Profile data/pages --redo data/pages/lind.html
biotope source generate .biotope/datasets/extracted/profile.jsonld --out graph/sources
```

- `biotope extract schema SCHEMA` prints, as JSON, the schema's `name`, record
  `key` and `revision` and the `json_schema` biotope derives from the class: what
  the extractor is asked for. It refuses a schema biotope cannot use, naming the
  field, and calls no extractor.
- `biotope extract try SCHEMA FILE...` runs the configured extractor on the given
  files and shows each record with its values and their evidence. It changes no
  file in the project. Use it to review a schema on sample documents. When it
  shows records, it notes the schema revision as tried on this machine, outside
  the project in `$XDG_CACHE_HOME/biotope/tried/` (by default `~/.cache`), so the
  note holds in every checkout of the project on this machine and in no other.
- `biotope extract run SCHEMA DATASET...` extracts every document of the given
  registered datasets, stores the records in `extracted/<schema>.jsonl` (or
  `--out PATH`) and registers that file as a dataset with status `processed`,
  derived from the input datasets. It keeps each document's records in
  `.biotope/progress/`, which Git ignores, as soon as that document is extracted,
  and writes the records file and the run state only when the run completes. An
  interrupted run leaves them unchanged; the next run reuses the documents it
  finished, gives the same output as an uninterrupted run, and reports every
  change since the last completed run. A dataset is named as for `--derived-from`: by
  its data path, its manifest path or its name. When `try` never showed the
  schema's current revision on this machine, `run` warns before
  extracting and lists the warning under `warnings` in its report; it still runs.
- `--redo FILE`, repeatable, extracts that document of the given datasets again
  although its inputs are unchanged, for example after the model missed or
  misread it. Its new records replace the old ones and carry `"redone": true` in
  their provenance; later runs reuse them.
- `biotope extract text FILE` prints biotope's text of a document: exactly what an
  extractor reads, and what the evidence's `start`, `end` and `page` refer to. PDF
  pages are separated by a form feed. Use it to check a value against its context.
- `try` and `run` take `--json` and then write one versioned JSON report to
  stdout. Both print `Extracting <n>/<total> <path>` to stderr when they send a
  document to the extractor, also with `--json`. The lines come in document
  order.

A document is a FileObject of a dataset whose path ends in `.pdf`, `.html`, `.htm`,
`.txt`, `.md` or `.markdown`. Other files of the dataset are left alone.

## Configuration

The extractor is configured in `.biotope/config.yaml` under `extraction`:

```yaml
extraction:
  extractor: llm
  endpoint: https://openrouter.ai/api/v1
  model: deepseek/deepseek-v4.1-flash
  key_env: OPENROUTER_API_KEY
  parallel: 4
```

- `extractor`: `llm` for the built-in extractor, or a project extractor named as
  `path/to/module.py:Class` (relative to the project root) or `package.module:Class`.
- `endpoint`, `model`, `key_env`: the built-in extractor's settings, all
  required. `endpoint` is the base URL of an OpenAI-compatible API. `key_env` names
  the environment variable that holds the API key. Biotope has no default model.
- `parallel`: how many documents `try` and `run` hand to the extractor at once,
  a whole number of at least 1; the default is 4. Set 1 for an endpoint with a
  tight rate limit. It changes neither the records, the report nor the order of
  the progress lines, and it is not an extractor setting, so changing it extracts
  nothing again.

Every other key under `extraction` is passed to a project extractor. The key's
value is never written to a file or shown in output. Without a model, or with an
unset key variable, `try` and `run` stop before any request and name what is
missing.

The built-in extractor sends each document's text in one request to
`<endpoint>/chat/completions` with a strict `json_schema` response format,
temperature 0, and a request for each value's verbatim quote. For a schema with
a record key it asks for a list of records; without one, for a single record or
null, so the model cannot return two. It makes up to four attempts, waiting 2, 4
and 8 seconds between them, when the endpoint times out, limits the rate, has a
server error, or answers with an empty, non-JSON or wrongly shaped message. A
null record is asked again in the same way, because a model that misses a
document often answers null; when every attempt gives null, the document has no
record and the report lists it as `empty`. When an attempt fails instead, the
document fails with that attempt's reason. Its
version is a digest of its prompt, so a changed prompt extracts every document
again.

Temperature 0 does not make a model's values reproducible: two runs on the same
document can differ. The stored records and their reuse keep a project stable;
re-extract a document with `--redo` only when its records are wrong.

## Extraction schemas

An extraction schema is a dataclass in the project, reviewed like the topology.
The class docstring says what kind of document it reads; each field's
`description` metadata tells the extractor what to fill and becomes the field's
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
    budget: str | None = field(metadata={"description": "The maximum budget per project, as written."})
```

A field's type is `str`, `int`, `float`, `bool` or a `Literal` of one of them,
optionally `| None`, or a list of one of them; an empty list means none. Declare
the class with `kw_only=True`, so that a field with a default can come before one
without; biotope ignores defaults. Biotope
refuses any other type before a request is sent, naming the field. Strict
structured output cannot express mappings, tuples, sets or `Any`; nested classes
are not supported either, so one record per item with a record key takes their
place.

**Record key.** `__record_key__` names the fields that tell a document's records
apart. A schema without one yields at most one record per document. Two records of
one document with equal key values, both null included, fail that document.

**Revision.** Biotope derives a JSON Schema from the class, the shape the
extractor is asked for: a `records` array whose items have one property per
field, with its type and description, and whose description states the record
key; without a record key, a single `record` object or null. The revision is the SHA-256 digest of
that JSON Schema's canonical form. It changes when a field, a type, a description,
the docstring or the record key changes. There is no freeze step: the revision of
the schema a run used is stored with each record.

## Project extractors

An extractor is any class that follows the `biotope.extraction.Extractor`
protocol:

```python
class Extractor(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def settings(self) -> Mapping[str, object]: ...
    def extract(self, document: Document, schema: Schema) -> list[dict[str, Any]]: ...
```

- The class is constructed with one argument, a dictionary of the configuration
  keys under `extraction` other than `extractor`. It raises `ValueError` for a
  missing or invalid setting.
- `settings` are the extractor's non-secret settings, such as a model or an
  endpoint, never a key. They must be JSON values. With the name and version, they
  are recorded in every record's provenance, and changing any of them extracts
  every document again.
- `extract` receives one `biotope.extraction.Document` with `path` (relative to
  the project root), `sha256`, `media_type` and `text`, biotope's text of the
  document, and the `biotope.extraction.Schema`, which gives `name`, `cls`,
  `description`, `key`, `fields` and `json_schema()`.
- It returns the document's records. Each record maps every schema field to
  `{"value": ..., "quote": "..."}`, or `{"value": ..., "locator": "..."}` for a
  value found by position, and a list field to a list of such objects. A quote is
  text copied from `document.text`. A locator is the extractor's own notation,
  such as `line 2`. A null value needs no evidence.
- With `parallel` above 1, `extract` is called for several documents at once
  from different threads, so it must not share unguarded state between calls.
- It raises `biotope.extraction.ExtractionError` with a reason when a document
  cannot be extracted. Biotope validates the records against the schema and
  aligns the quotes; an extractor never computes positions.

## Stored output

`extract run` writes one JSON Lines file, by default `extracted/<schema>.jsonl`
(`FundingRound` becomes `funding_round.jsonl`), sorted by record ID. Commit it
with the project. Each line is one record:

```json
{
  "id": "data/calls/call.pdf#round=\"Full proposal\"",
  "document": "data/calls/call.pdf",
  "supported": true,
  "values": {
    "deadline": {
      "value": "30 April 2027",
      "evidence": {"quote": "Full proposal 30 April 2027 1 500 000 EUR", "locator": null,
                   "aligned": true, "start": 528, "end": 569, "page": 2,
                   "occurrences": 1, "weak": []}
    }
  },
  "provenance": {
    "document_sha256": "0e2faf46…",
    "media_type": "application/pdf",
    "conversion": 2,
    "schema": "FundingRound",
    "schema_revision": "065fb9fb…",
    "extractor": {"name": "llm", "version": "5c0d81e2a7f4",
                  "settings": {"endpoint": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-v4.1-flash"}}
  }
}
```

- **ID.** The document's path, then `#` and each key field as
  `name=<JSON value>`, joined by `;`, with each value as the schema types it, so
  `1` and `1.0` of a `float` field are one key. Without a record key, the path alone. An ID
  depends only on the path and the key values, never on a record's position, so it
  stays the same when the same key values return in another order. After a
  document moves, its records' IDs follow the new path.
- **Values.** `values` holds every schema field. A scalar field is an object with
  `value` and `evidence`; a list field is a list of such objects.
- **Evidence.** `quote` is the extractor's quote and `locator` its locator.
  `aligned` says whether biotope found the quote in its text of the document,
  first exactly and then ignoring whitespace, hyphens and case. `start` and `end`
  are character offsets into that text and `page` is the PDF page, from 1.
  `occurrences` counts how often the quote occurs in the text, with the same
  matching. `weak` lists why an aligned quote may not prove its value: `short`,
  under 10 characters ignoring whitespace and hyphens; `repeated`, under 30 such
  characters and found more than once; `running head`, found only in lines of a
  PDF that recur, digits aside, on more than half of its pages, when it has at
  least three: running heads, footers, page numbers and mastheads. The list is
  empty for a quote without these reasons. Such a quote is found, but it may not show
  that the value is right: a short quote, such as a label, can support many
  values, and a repeated one may come from another part of the document, such as
  a menu. A longer quote found several times, such as a title printed twice, is
  not weak. A running head says nothing about a record, but a model may quote one
  when it finds nothing better. Biotope flags such quotes instead of removing the
  lines from its text, so the text stays the one the extractor read and stored
  offsets stay valid. With several occurrences `start` and `page` give only the first. `weak` is null for an
  unaligned quote and a locator. A value
  read from a table quotes the table's whole row. A value whose quote cannot be
  found keeps `aligned: false` and is listed in the run report. A value with
  neither a quote nor a locator has `evidence: null`; when the value is not null,
  it is kept and listed in the run report with the unaligned values.
- **Supported.** `supported` is false when more than half of the record's
  non-null values are unaligned, have no evidence or are quoted only from running
  heads. Such a record usually means the extractor answered from memory or from
  page furniture instead of from the document's content. It is kept,
  and the report lists it for review.
- **Provenance.** The document's digest and media type, the version of
  biotope's conversion of the document to text (`conversion`), the schema's name and
  revision, and the extractor's name, version and settings. `redone: true` marks
  records extracted again with `--redo`.

**Registered dataset.** The records file is registered at
`.biotope/datasets/extracted/<schema>.jsonld`, with status `processed`,
`prov:wasDerivedFrom` the input datasets and a RecordSet keyed by `id`. It has no
`creator` or `license`: biotope cannot know them, and the placeholders the baker
would write describe nothing.
Croissant-baker describes the file. Biotope then writes the RecordSet's fields from
the schema, because the baker infers fields from the values present: it would drop
a field that is null in every record and describe lists as opaque arrays. Each
value field carries the schema's description, type and nullability, and lists are
marked `cr:isArray`, so `biotope source generate` produces typed, nested record
classes into which the stored records load unchanged. The extractor's settings are
described when they hold a single value, such as text or a number; a setting that
holds a list or an object stays in the records without a field, and an extractor
without such settings gets no `settings` field. Do not edit this manifest by hand:
the next run that finds it no longer describes the records or the schema writes it
again.

**Run state.** `.biotope/extraction/extracted/<schema>.json` records, per
document, the digest, schema revision and extractor that produced its stored
records, including documents that gave none. Commit it.

**Document texts.** Biotope's text of each document is cached in
`.biotope/texts/<sha256>-<conversion>.txt`, which ignores itself in Git, because
the texts can hold copyrighted full text. `<conversion>` numbers the version of
biotope's conversion, so a biotope that converts differently makes new texts.
After such a change, the next run aligns the quotes of each reused record again
to the new text, without a request, and records the new `conversion`. A missing
document's records keep the offsets of the conversion their provenance names.
Evidence offsets refer to this text. PDF pages are
separated by a form feed. HTML is reduced to its visible text, one block per
line, without `nav` elements and without the `header` and `footer` elements that
are not inside `main`, `article` or `section`: a page's menus, breadcrumbs and
footer are not content, and a model would quote them as values.
A deleted cache is made again from the documents when needed. A clone without the
documents can build from the records but cannot check their quotes again.

## Reuse and the run report

A document is extracted again only when its digest, the schema revision, or the
extractor's name, version or settings change. Otherwise its stored records are
reused without a request, also after `biotope mv` moved it. A registered document
whose file is missing, cannot be read or fails keeps its stored records. When the records file itself is
missing, every document is extracted again. A document removed from its
dataset, or a dataset left out of the command, loses its records.

The report lists each document as `extracted`, `empty` (extracted, but the
extractor returned no record), `unsupported` (extracted, but at least one record
is not `supported`), `reused`, `failed` or `missing`, with its reason; every record
that is not supported, with its number of non-null values and how many of them are
unaligned or quoted only from running heads (`unsupported`); every non-null value whose quote is unaligned or that has no
evidence (`unaligned`); every value with weak evidence and its reasons, `short`,
`repeated` or `running head` (`weak`); the number of non-null values and how many are aligned,
unaligned and weak (`counts`); the record IDs that disappeared and appeared; each
old ID with its new one for documents that moved; and the output files that Git
ignores (`ignored`), which should be committed with the project. `try` reports
`unaligned`, `weak`, `unsupported` and `counts` for its files as well, and lists
a file as `extracted`, `empty`, `unsupported` or `failed`. `run` also reports
`warnings`, such as a schema revision `try` never showed. Redo or drop every
`unsupported` document: its stored records stay until you do. Check every `empty` document: a model's miss
looks the same as a document that states nothing, and `--redo` asks again. A failed document keeps the records it had, and the others are stored. The
run exits nonzero when a document failed or is missing.
