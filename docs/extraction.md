# Documents

Papers, web pages, contracts and other [unstructured documents](get-started.md#concepts) become records through extraction. The agent writes one extractor for each kind of document. Biotope runs it, keeps the quote or location behind each value, and stores the records as a dataset that the graph reads like any table.

## What you decide

- **Which services may read the documents**, such as a model API, and how API keys are supplied. The agent asks before any document goes to an external service. Keys stay in environment variables.
- **What to extract.** The agent proposes a schema: the kind of record, its fields, and the question each field serves. It runs the schema on a few sample documents and shows you each value with its quote. It extracts all documents only after you approve, and asks again after every change to the schema.

## The commands

```bash
uv run --project graph biotope extract try papers data/papers/smith2024.pdf
uv run --project graph biotope extract run
uv run --project graph biotope extract run papers --redo data/papers/smith2024.pdf
```

- `extract try NAME FILE...` runs one extraction on the given files and shows the records with their evidence. It changes nothing.
- `extract run` runs every extraction, or the ones you name, and stores the records.
- `--redo FILE` extracts that document again.

## Where the records are

Each extraction stores its records in `data/extracted/<name>.jsonl`, one record per line. Commit the file. Each value keeps its quote or location, and each record names its document, the schema revision and the extractor:

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

## When a document is extracted again

A run extracts a document only when it is new or changed, or when the schema or the extractor changed. Otherwise it reuses the stored records. Extraction usually calls a paid model, so a change to the schema means model calls for every document. An interrupted run can be started again: it reuses the documents it finished.

## Review the records

- The run report lists each document as extracted, empty, reused or failed, and the record IDs that appeared and disappeared.
- `git diff data/extracted/` shows every changed value, including those of records that kept their ID.
- Biotope checks that each record fits the schema. It does not check that a quote is in the document or that a value is right. Compare some values with their quotes.
