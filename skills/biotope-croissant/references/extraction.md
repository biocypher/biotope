# Extracting records from documents

Documents, such as papers, saved web pages and calls, go through extraction: an extractor reads each document under an extraction schema and returns records whose values carry their evidence. `biotope extract run` stores them and registers them as a processed dataset, which you then generate and map like a table. The contracts are in the Biotope documentation page "Extraction".

## Who decides what

- The user decides which documents may go to an external model. Send only public documents, such as published papers, public web pages and public calls. When a document is internal, confidential or of unknown status, do not extract it with a model: ask the user, and transcribe its facts by hand as a document source if they agree.
- The user decides what the schema extracts: which kinds of document, which fields, what each field means and which fields identify a record. You propose; the user approves. A field description is a scientific definition, like a topology description.
- You decide the engineering: field types, the record key's mechanics, the module layout and the commands. The model and endpoint are the project's choice; ask when the configuration does not name them, and never choose a default.

## Steps

1. Register the documents with `biotope add <data-path> --json`, as in Step 3.
1. Read the purpose, its requirements and a few sample documents of each kind. Propose one schema per kind of document, as a dataclass in `extraction/<kind>.py`: a docstring saying what the document is, one field per value a requirement needs, and a `description` for every field that says exactly what to fill and what not to (for example "organisms whose samples the study analysed", not "organisms"). Declare `__record_key__` when a document holds several records, such as the rounds of a call or the comparisons of a study.
1. Check that `.biotope/config.yaml` has an `extraction` section with the extractor, endpoint, model and `key_env`. The key stays in the environment variable; never write it into a file, a command line or a message.
1. Run `biotope extract try extraction/<kind>.py:<Class> <sample>...` on two or three representative documents. Show the user the schema and the `try` output: each value, its quote and whether the quote was found in the document.
1. Revise the schema with the user until they approve it. Every change to a field, a description or the key changes the schema's revision and re-extracts every document, so settle the schema on samples first.
1. After the user approves, run `biotope extract run extraction/<kind>.py:<Class> <dataset>... --json`. Read the report: fix or report every `failed` and `missing` document, check each unaligned value against the document, and explain disappeared and appeared record IDs.
1. Run `biotope source generate .biotope/datasets/extracted/<kind>.jsonld --out graph/sources` and continue with Step 4. Each record's `id` is the identity to keep; a loader yields one record per line and cites the document, the record's `document_sha256` as the version, and the value's page and quote as the location.

Never edit the extracted records or their manifest by hand: a later run rewrites them. Correct a wrong value through the schema and a new run, or exclude the record in a mapping against a declared policy.

Run `biotope extract run` again after documents change; unchanged documents are reused without a model call, and the report says what changed.
