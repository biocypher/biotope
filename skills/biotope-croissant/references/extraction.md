# Extracting records from documents

Documents, such as papers, saved web pages and calls, go through extraction: an extractor reads each document under an extraction schema and returns records whose values carry their evidence. `biotope extract run` stores them and registers them as a processed dataset, which you then generate and map like a table. The contracts are in the Biotope documentation page "Extraction".

## Who decides what

- The user decides which documents may go to an external model. Send only public documents, such as published papers, public web pages and public calls. When a document is internal, confidential or of unknown status, do not extract it with a model: ask the user, and transcribe its facts by hand as a document source if they agree.
- The user decides what the schema extracts: which kinds of document, which fields, what each field means and which fields identify a record. You propose; the user approves. A field description is a scientific definition, like a topology description.
- You decide the engineering: field types, the record key's mechanics, the module layout and the commands. The model and endpoint are the project's choice; ask when the configuration does not name them, and never choose a default.

## Steps

1. Register the documents with `biotope add <data-path> --json`, as in Step 3.
1. Read the purpose and its competence questions or user stories, then a few sample documents of each kind. Derive the fields from the questions, not from the documents' layout: list each question a kind of document must help answer and the values it needs, and propose one field per value. A field no question needs is left out; a question no field serves is named as a gap. Write one schema per kind of document as a dataclass in `extraction/<kind>.py`, declared `@dataclass(frozen=True, kw_only=True)`: a docstring saying what the document is, and a `description` for every field that says exactly what to fill and what not to (for example "organisms whose samples the study analysed", not "organisms"). Declare `__record_key__` when a document holds several records, such as the rounds of a call or the comparisons of a study.
1. Check that `.biotope/config.yaml` has an `extraction` section with the extractor, endpoint, model and `key_env`. The key stays in the environment variable; never write it into a file, a command line or a message.
1. Run `biotope extract try extraction/<kind>.py:<Class> <sample>... --json` on two or three representative documents. It prints one progress line per document to stderr; wait for it to finish instead of polling.
1. Check the `try` output yourself before showing it. For a sample of values, and for every value in `unaligned` and `weak`, read the quote and its context in `biotope extract text <file>` (the evidence's `start` and `end` are offsets into that text) and ask whether the value answers the field's description. A `weak` quote is short or occurs more than once: it was found, but it does not show that the value is right, so judge it from the context. Where values are wrong, sharpen the field descriptions and run `try` again.
1. Show the user each field with the question it serves, and the `try` output: each value, its quote, whether the quote was found, the weak evidence, and what you checked and changed. Revise the schema with the user until they approve it. Every change to a field, a description or the key changes the schema's revision and re-extracts every document, so settle the schema on samples first.
1. After the user approves, run `biotope extract run extraction/<kind>.py:<Class> <dataset>... --json`. Read the report: fix or report every `failed` and `missing` document, check each `unaligned` and `weak` value against the document text, and explain disappeared and appeared record IDs. Fix `ignored` files: they must be committed, so add an exception to `.gitignore`.
1. When a document's records look wrong, such as no records where the document clearly has some, run the same command again with `--redo <file>` for that document. A model's values vary between runs, so re-extract only documents whose records are wrong, and tell the user which ones you re-extracted and why. When the same document fails again, the schema or its descriptions need work: go back to the user.
1. Run `biotope source generate .biotope/datasets/extracted/<kind>.jsonld --out graph/sources` and continue with Step 4. Each record's `id` is the identity to keep; a loader yields one record per line and cites the document, the record's `document_sha256` as the version, and the value's page and quote as the location.

Never edit the extracted records or their manifest by hand: a later run rewrites them. Correct a wrong value through the schema and a new run, or exclude the record in a mapping against a declared policy.

Run `biotope extract run` again after documents change; unchanged documents are reused without a model call, and the report says what changed.
