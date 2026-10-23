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
biotope extract try extraction/schemas.py:Profile data/pages/lind.html
biotope extract run extraction/schemas.py:Profile data/pages
biotope source generate .biotope/datasets/extracted/profile.jsonld --out graph/sources
```

- `biotope extract try SCHEMA FILE...` runs the configured extractor on the given
  files and shows each record with its values and their evidence. It changes no
  file in the project. Use it to review a schema on sample documents.
- `biotope extract run SCHEMA DATASET...` extracts every document of the given
  registered datasets, stores the records in `extracted/<schema>.jsonl` (or
  `--out PATH`) and registers that file as a dataset with status `processed`,
  derived from the input datasets. A dataset is named as for `--derived-from`: by
  its data path, its manifest path or its name.
- Both take `--json` and then write one versioned JSON report to stdout.

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
```

- `extractor`: `llm` for the built-in extractor, or a project extractor named as
  `path/to/module.py:Class` (relative to the project root) or `package.module:Class`.
- `endpoint`, `model`, `key_env`: the built-in extractor's settings, all
  required. `endpoint` is the base URL of an OpenAI-compatible API. `key_env` names
  the environment variable that holds the API key. Biotope has no default model.

Every other key under `extraction` is passed to a project extractor. The key's
value is never written to a file or shown in output. Without a model, or with an
unset key variable, `try` and `run` stop before any request and name what is
missing.

The built-in extractor sends each document's text in one request to
`<endpoint>/chat/completions` with a strict `json_schema` response format,
temperature 0, and a request for each value's verbatim quote. It retries
timeouts, rate limits and server errors twice.

## Extraction schemas

An extraction schema is a dataclass in the project, reviewed like the topology.
The class docstring says what kind of document it reads; each field's
`description` metadata tells the extractor what to fill and becomes the field's
description in the registered dataset.

```python
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True)
class FundingRound:
    """One funding round of a call for proposals."""

    __record_key__: ClassVar[tuple[str, ...]] = ("round",)

    round: str | None = field(metadata={"description": "The round's name as the call gives it."})
    deadline: str | None = field(metadata={"description": "The round's submission deadline, as written."})
    budget: str | None = field(metadata={"description": "The maximum budget per project, as written."})
```

A field's type is `str`, `int`, `float`, `bool` or a `Literal` of one of them,
optionally `| None`, or a list of one of them; an empty list means none. Biotope
refuses any other type before a request is sent, naming the field. Strict
structured output cannot express mappings, tuples, sets or `Any`; nested classes
are not supported either, so one record per item with a record key takes their
place.

**Record key.** `__record_key__` names the fields that tell a document's records
apart. A schema without one yields at most one record per document. Two records of
one document with equal key values, both null included, fail that document.

**Revision.** Biotope derives a JSON Schema from the class: a `records` array
whose items have one property per field, with its type and description, and
whose description states the record key. The revision is the SHA-256 digest of
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
  "values": {
    "deadline": {
      "value": "30 April 2027",
      "evidence": {"quote": "Full proposal 30 April 2027 1 500 000 EUR", "locator": null,
                   "aligned": true, "start": 528, "end": 569, "page": 2}
    }
  },
  "provenance": {
    "document_sha256": "0e2faf46…",
    "media_type": "application/pdf",
    "schema": "FundingRound",
    "schema_revision": "065fb9fb…",
    "extractor": {"name": "llm", "version": "1",
                  "settings": {"endpoint": "https://openrouter.ai/api/v1", "model": "deepseek/deepseek-v4.1-flash"}}
  }
}
```

- **ID.** The document's path, then `#` and each key field as
  `name=<JSON value>`, joined by `;`. Without a record key, the path alone. An ID
  depends only on the path and the key values, never on a record's position, so it
  stays the same when the same key values return in another order. After a
  document moves, its records' IDs follow the new path.
- **Values.** `values` holds every schema field. A scalar field is an object with
  `value` and `evidence`; a list field is a list of such objects.
- **Evidence.** `quote` is the extractor's quote and `locator` its locator.
  `aligned` says whether biotope found the quote in its text of the document,
  first exactly and then ignoring whitespace, hyphens and case. `start` and `end`
  are character offsets into that text and `page` is the PDF page, from 1. A value
  read from a table quotes the table's whole row. A value whose quote cannot be
  found keeps `aligned: false` and is listed in the run report. A null value
  without evidence has `evidence: null`.
- **Provenance.** The document's digest and media type, the schema's name and
  revision, and the extractor's name, version and settings.

**Registered dataset.** The records file is registered at
`.biotope/datasets/extracted/<schema>.jsonld`, with status `processed`,
`prov:wasDerivedFrom` the input datasets and a RecordSet keyed by `id`.
Croissant-baker describes the file. Biotope then writes the RecordSet's fields from
the schema, because the baker infers fields from the values present: it would drop
a field that is null in every record and describe lists as opaque arrays. Each
value field carries the schema's description, type and nullability, and lists are
marked `cr:isArray`, so `biotope source generate` produces typed, nested record
classes. Do not edit this manifest by hand: the next run that changes the records
writes it again.

**Run state.** `.biotope/extraction/extracted/<schema>.json` records, per
document, the digest, schema revision and extractor that produced its stored
records, including documents that gave none. Commit it.

**Document texts.** Biotope's text of each document is cached in
`.biotope/texts/<sha256>.txt`, which ignores itself in Git, because the texts can
hold copyrighted full text. Evidence offsets refer to this text. PDF pages are
separated by a form feed; HTML is reduced to its visible text, one block per line.
A deleted cache is made again from the documents when needed. A clone without the
documents can build from the records but cannot check their quotes again.

## Reuse and the run report

A document is extracted again only when its digest, the schema revision, or the
extractor's name, version or settings change. Otherwise its stored records are
reused without a request, also after `biotope mv` moved it. A registered document
whose file is missing keeps its stored records. A document removed from its
dataset, or a dataset left out of the command, loses its records.

The report lists each document as `extracted`, `reused`, `failed` or `missing`,
with its reason; every value whose quote is unaligned; the record IDs that
disappeared and appeared; and each old ID with its new one for documents that
moved. A failed document keeps the records it had, and the others are stored. The
run exits nonzero when a document failed or is missing.
