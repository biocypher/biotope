# Extracting records from unstructured documents

Unstructured documents, such as paper PDFs, scraped web pages and contracts, go through extraction. You write one extractor per kind of document in the project's graph workspace, and Biotope runs it: it hands each matched document to the extractor, validates the records, reuses unchanged ones, stores them and registers them as a processed dataset, which you then generate and map like a table. The interfaces you write against are in "Contract" below.

## Contents

- Who decides what
- Approach
- Steps
- Contract: commands, declaring extractions, schemas, extractors, stored records, reuse and the report

## Who decides what

- The user decides which services may process the documents and how keys are supplied. Ask before any document goes to an external service. Keys stay in environment variables the extractor reads; never write one into a file, a command line or a message.
- The user decides what the schema extracts: which kinds of document, which fields, what each field means and which fields identify a record. You propose; the user approves. A field description is a scientific definition, like a topology description.
- You decide the engineering: how each kind of document is read, the extractor's code, field types and the record key's mechanics. You may discuss organising the data folder with the user, so that each kind of document is easy to route.

## Approach

- Sort the documents by how they are built before you run `biotope add` and before writing any extractor: which files are structured and which are unstructured documents, and which documents share a structure, such as papers, a website's profile pages or contracts. A suffix or folder alone does not tell: a folder of papers can hold PDFs and text files of one kind, and tab-separated `.txt` files are tables. One kind of document gets one extractor.
- Read structure with code and give a model only what needs language. Headings, tables, page numbers and the elements of a page are read with an established library; a model gets only the passages a value must be read from.
- Fail loudly: when a document lacks the structure the extractor expects, raise `ExtractionError` with the reason, rather than return partial or empty records.
- Keep evidence with each value: the quote the value comes from, or a locator such as a page and section, so a reader can check it and a loader can cite it. A quote is the document's text as a reader sees it, not its markup.

## Steps

1. Register the documents with `biotope add <data-path> --json`, as in Step 3.
1. Read the purpose and the questions agreed in Step 2, then a few sample documents of each kind. Derive the schema from the questions, not from the documents' layout:
   - Write each question as the query a user would run, such as "which PIs work on topic X", "which calls accept PhDs from year Y" or "which studies compare day 3 with day 0 in mouse". Name the field each query filters, searches or sorts on, and its value type. A query needs a field with short, comparable values, such as a list of topics, methods or scales, or a number or `Literal` for a range or category; a prose field can be read but not filtered. Propose these fields yourself, without waiting for the user to ask, and say which query each serves.
   - List the values each answer needs to be read correctly, such as the direction of a change, the reference group, and whether the groups are the same individuals, and propose one field per value.
   - A field no question needs is left out; a question no field serves is named as a gap.
   - Decide which records the purpose needs. A record stands for something the purpose asks about and the document itself reports. Say in the docstring which records to extract and which to leave out. Never ask for records the document does not report, and never construct one from parts of the document.
1. Copy `graph/extraction/template.py` to `graph/extraction/<kind>.py` for each kind of document and delete its first line, `# biotope:placeholder`. Write the schema and the extractor as "Schemas" and "Extractors" below describe. Shared reading code goes in a module of its own in `graph/extraction/`, imported with a relative import.
1. List each extraction in `graph/extraction/__init__.py`, as "Declaring extractions" below describes. Run `biotope graph check`; it type-checks the extraction code.
1. Run `biotope extract try <name> <sample>... --json` on two or three representative documents, including the one with the most records, in the foreground with a long timeout.
1. Check the `try` output yourself before showing it: compare each record with its document, check a sample of values against their quotes or locators, list the records that should not exist and the ones that are missing, and treat an `empty` document as a miss until the document shows it states nothing. Where values or records are wrong, fix the extractor or sharpen the descriptions and run `try` again.
1. Show the user each field with the question it serves, and the `try` output: each value with its evidence, the records you judged wrong or missing, and what you checked and changed. Revise the schema with the user until they approve it.
1. Any change to the schema after the user approved it makes a new revision: run `try` again on the same samples, check it, and get the user's approval before `run`. Whenever the extractor's behavior changes, raise its `version`, so the next run extracts every document again.
1. After the user approves, run `biotope extract run --json`, in the foreground as for `try`; it runs every listed extraction, or the ones you name. When a run is interrupted, run it again: it reuses the documents it finished. Read the report: fix or report every `failed` document, check every `empty` one, and explain disappeared and appeared record IDs. Then review `git diff data/extracted/`: a record that keeps its ID while its values change is in no list of the report. Report `ignored` files to the user: they must be committed, so `.gitignore` needs an exception.
1. Check the stored records of every document as in the `try` check. Re-extract each document whose records you judge wrong with `--redo <file>`, and check it again. When a document is still wrong, the schema or the extractor needs work. In the hand-over, list each document you re-extracted, why, and whether it is now right.
1. Continue with Step 5, which generates the records file like any other manifest: `biotope source generate .biotope/datasets/data/extracted/<name>.jsonl.jsonld --out graph/sources`. Each record's `id` is the identity to keep; a loader yields one record per line and cites the document, the record's `document_sha256` as the version, and the value's quote or locator as the location.

Never edit the extracted records or their manifest by hand: a later run rewrites them. Correct a wrong value through the extractor or the schema and a new run, or exclude the record in a mapping against a declared policy.

## Contract

### Commands

- `biotope extract try NAME FILE...` runs one listed extraction on the given files and shows each record with its values and evidence. It changes nothing in the project, and the files need no dataset yet.
- `biotope extract run [NAME...]` runs the named extractions, or every listed one, stores each one's records and registers them as a dataset. `--redo FILE`, repeatable, extracts that document again although its inputs are unchanged.
- With `--json`, both write one JSON report to stdout. Both print `Extracting <n>/<total> <path>` to stderr for each document they hand to an extractor.

### Declaring extractions

`graph/extraction/__init__.py` lists every extraction:

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

- `name` starts with a lowercase letter and holds only lowercase letters, digits and underscores. It names the records file, `data/extracted/<name>.jsonl`.
- `files` are path patterns relative to the project root, as `pathlib` globs them. They route documents by folder or name, such as `data/pages/*.html` or `data/inbox/contract_*.pdf`. Hidden files and annotation files never match. A pattern that matches no file fails the run, and so does a matched file that no dataset describes, such as a copy `biotope add` skipped as identical to another file. Narrow the patterns to leave such copies out.
- `parallel`, 1 by default, is how many documents the extractor gets at once, each in its own thread. Above 1, guard any library that is not thread-safe with a lock, or keep it at 1.

Biotope imports the list through the graph workspace, so extraction code can import other project modules, and checks every entry before it reads a document. `graph check`, `extract try` and `extract run` refuse a listed extraction whose schema or extractor file still starts with `# biotope:placeholder`; an unlisted template is ignored.

### Schemas

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

- The docstring says what the document is and which records to extract. Each field's `description` says exactly what to fill and becomes the field's description in the registered dataset.
- A field's type is `str`, `int`, `float`, `bool` or a `Literal` of values of one of these types, optionally `| None`, or a list of one of them. Biotope refuses any other type, a schema without fields, and a field named `id` or `document`, which every stored record already has.
- `__record_key__` names the fields that tell a document's records apart; a key field cannot be a list. Without a key, a document yields at most one record. Two records of one document with equal key values fail that document.
- The schema's revision is the SHA-256 digest of its name, docstring, record key and fields with their types and descriptions. Rewording the docstring or a description makes a new revision, and the next run extracts every document again.

### Extractors

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

- `name`, `version` and `settings` are class attributes, so Biotope reads them without creating the extractor. `settings` holds the JSON values that shape the output, such as the model, never a key. All three go into every record's provenance.
- Biotope creates the extractor with no arguments, once per run and only when a document needs extraction, so a run that reuses every record needs no key. An extractor that cannot start, for example without its key, raises `ExtractionError` from `__init__`, and every document it would have read fails with that reason.
- `extract` gets a `Document`, with the file's `path` and `sha256`, and the parsed `Schema`, with its `name`, `description`, `key` and `fields`. Biotope converts no document: `extract` reads the file as its kind needs.
- `extract` returns the document's records, each a dict with exactly the schema's fields. Each value is `{"value": ..., "quote": "..."}`, `{"value": ..., "locator": "..."}` or an object with both, and a list field holds a list of these. A locator is the extractor's own notation, such as `page 3` or `row 14`. A value with neither has no evidence.
- Biotope validates each value against its field's type without coercion, so `"3"` fails an `int` field. It does not check that a quote occurs in the document or that a value is right: reviewing the records is your work and the user's.

### Stored records

`biotope extract run` writes `data/extracted/<name>.jsonl`, one record per line, sorted by ID. It is committed with the project; the `.gitignore` that `biotope init` writes keeps `data/extracted/` in git. Loaders read this shape:

```json
{
  "id": "calls/call.md#round=\"Full proposal\"",
  "document": "data/calls/call.md",
  "values": {
    "round": {"value": "Full proposal", "evidence": {"quote": "| Full proposal | 30 April 2027 |", "locator": null}},
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

- `id`: the name of the document's dataset folder and the document's path within it, such as `pages/lind.html`, or the file name for a single-file dataset; with a record key, then `#` and each key field as `name=<JSON value>`, joined by `;`. A value is written as the schema types it, so `1` and `1.0` of a `float` field are one key. Documents of two datasets with the same name and path would share an ID, so the run refuses them.
- `document`: the document's path from the project root.
- Each value's `evidence`: the extractor's `quote` and `locator`, or `null` when it gave neither.

The records file is registered as `.biotope/datasets/data/extracted/<name>.jsonl.jsonld`, with status `processed`, `prov:wasDerivedFrom` the datasets of its documents, `isBasedOn` each document the extraction read with the checksum it had, `biotope:schemaRevision` and `biotope:extractor` the schema revision and extractor of the run, and a RecordSet keyed by `id`. Its fields are `id`, `document` and one field per schema field, with the schema's types and descriptions, so `source generate` produces one flat record class. The quotes, locators and provenance stay in the records file for the loader's evidence. Its creator and license come from the project defaults that `biotope config set-project-metadata` sets. Its annotation file, `data/extracted/<name>.jsonl.biotope.yaml`, overrides them and holds other dataset fields, for example `biotope annotate set data/extracted/<name>.jsonl description="..."`. A folder dataset that holds the records file, as `biotope add data` holds `data/extracted/`, leaves the file out. `source generate` writes no package for a document an extraction has read, and reports a package generated for it before the run as orphaned: delete that package.

The records file always sits at `data/extracted/<name>.jsonl`, and `biotope mv` refuses to move it. To rename an extraction, rename it, run it and remove the old records file with `biotope rm data/extracted/<old name>.jsonl`. To drop an extraction, delete it from the list and remove its records file the same way; `biotope rm` also removes its description, so its documents get packages again.

### Reuse and the report

A document is extracted again only when its digest, the schema revision, or the extractor's `name`, `version` or `settings` change, or when `--redo` names it. Otherwise its stored records are reused without creating the extractor, also after `biotope mv` moved it. A document that fails keeps its stored records.

The records mirror the files the patterns match now: run `biotope extract run` again after documents change. A new file joins, a removed one loses its records, and a moved file keeps them only while a pattern still matches it. A moved document's records keep their IDs when its dataset's name and its path within the dataset stay the same, as when a whole dataset folder moves; otherwise they take IDs from the new path, so check any mapping that joins on them.

The report lists, per extraction, each document as `extracted`, `empty` (no record), `reused` or `failed` with its reason; the record IDs that disappeared and appeared; each moved ID with its new one; and, under `ignored`, the output files git ignores. The run exits nonzero when a document failed.
