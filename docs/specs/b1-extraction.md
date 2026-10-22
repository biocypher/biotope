# B1: Extraction

Needs: none · Roadmap decisions: 1–8, 14 · Research: [`docs/research/b1-extraction.md`](../research/b1-extraction.md)

## Goal and why

After B1, a project turns local documents (PDF, HTML, plain text) into a stored, versioned structured dataset, which then enters `biotope add` like any other file. Each field of each record carries its evidence, and each record names the document, the reviewed extraction schema revision and the extractor that produced it.

Today a document becomes a document source whose facts an agent transcribes by hand (`_document_hint` in `biotope/graph/render.py`). That does not scale to REACH's CHC profile pages, ERC calls or InTRAC's papers, and it leaves no checkable link between a value and the text it came from. B1 is tested on those three kinds of document.

The roadmap decisions this milestone respects:

- Decision 1: biotope "is never a fetcher or scraper". Documents are local files.
- Decision 2: "Extraction is a stage before `add`. A raw document goes through an extractor into a stored, derived dataset (`prov:wasDerivedFrom`, status `processed`). Croissant-baker then describes it like any other file. `graph build` stays deterministic and offline."
- Decision 3: "An extractor takes documents and a frozen extraction schema, and returns records that match the schema. Each record points to its document and each field carries its evidence, the quoted span or a locator. An extractor declares its name and version."
- Decision 4: "A document is extracted again only when one of these changes": document hash, schema revision, extractor name and version, model.
- Decision 5: "The endpoint URL is project configuration and may be written literally, since it is not a secret. The key always comes from an environment variable that the configuration names."
- Decisions 6 and 14: only public documents go to an external model, and tests use only public material.
- Decision 7: "People review artefacts, not records." An agent proposes the extraction schema; a person reviews and freezes it.

## Scope

- The command group `biotope extract` with `try`, `freeze` and `run`.
- Extraction schemas, kept apart from the topology, with frozen revisions recorded in the project.
- The extractor contract, the built-in `llm` extractor, and project extractors loaded by import path.
- Document text for PDF (`pypdfium2`), HTML (BeautifulSoup on a declared selector), plain text and Markdown, stored so that evidence offsets stay checkable.
- Quote alignment to character offsets, as biotope's own code.
- Reuse of stored results, and registration of the output as a derived, processed dataset.
- The optional dependency group `biotope[extract]`, which CI's test job and the install command in `AGENTS.md` add with `--extra extract`, the pytest marker `live`, and a docs page `docs/extraction.md` (in both nav files) with the two supported configurations.
- `skills/biotope-croissant`: the agent proposes each extraction schema and the user reviews it, under the skill's ownership rule.

## Non-goals

- The rule-based extractor. B1 has only a test fake standing in for it.
- Evaluation: gold sets, precision or recall measures, model comparisons beyond the research note.
- Fetching, downloading or scraping; internal or confidential documents and per-source policies (decision 6).
- Identity and precedence across records or documents (B2); the ID registry, human decisions on records and release history (B3).
- OCR, scanned PDFs, table or layout recovery.
- A default model, and the libraries the research note rejects: LangExtract, instructor, outlines, the `openai` SDK, docling, marker, pymupdf4llm, trafilatura and markitdown.

## Interfaces

**Commands.** Each runs from the project root and takes `--json`, which writes one versioned document to stdout as `CONTRIBUTING.md` describes.

- `biotope extract try <draft> <file>...` runs the configured extractor with a draft schema on the given files and prints each record with its evidence and alignment. It writes nothing in the project.
- `biotope extract freeze <draft> --name <name> --reason "<text>"` validates the draft and records it as the current revision of the schema `<name>`. An invalid draft is refused with its reason, and nothing is written.
- `biotope extract run <name> <dataset>... [--out <dir>]` extracts every document of the given registered datasets, named as `biotope add --derived-from` accepts them, under the current revision of `<name>`. It writes the output dataset to `<dir>`, by default `extracted/<name>/`, and registers it. The output is committed: it is the versioned record of what the extractor returned, which a later call need not reproduce. The default lies outside `data/`, which `biotope init` makes git ignore. It exits 1 when any document failed and 0 otherwise; unaligned fields alone do not fail a run.
- `biotope graph check`, `quality` and `build` never call an extractor.

**Configuration,** under the key `extraction` in `.biotope/config.yaml`:

- `extractor`: `llm` (the default) or `<module>:<attribute>`, importable with the project root on the path, naming a callable that takes the `extraction` mapping and returns an extractor.
- `endpoint`: the base URL of an OpenAI-compatible API, or `env:<NAME>` to read it from the variable `NAME`.
- `api_key_env`: the name of the variable that holds the key.
- `model`: required by `llm`. Biotope has no default model.

The supported configurations, documented in `docs/extraction.md`: REACH and InTRAC use `endpoint: https://openrouter.ai/api/v1`, `api_key_env: OPENROUTER_API_KEY`, `model: anthropic/claude-haiku-5.5`. The second is `endpoint: env:HMGU_AGENTS_ENDPOINT`, `api_key_env: HMGU_AGENTS_API_KEY`, `model: qwen38`.

**Extraction schema,** a YAML file:

- `document`: one sentence naming the kind of document, which the prompt uses.
- `html_selector` (optional): the CSS selector of the element whose text is read from an HTML document.
- `record`: a JSON Schema for one record, an `object` whose `properties` each have a `description`. Allowed are `string`, `number`, `integer`, `boolean`, `enum`, `array`, nested `object`, and a union with `null` for a value that may be absent. `freeze` refuses any other keyword, such as `$ref`, `pattern` or `oneOf`.

A document yields zero or more records. Biotope derives two schemas from `record`, both of the shape `{"records": [<record>]}` with every leaf replaced:

- The **request schema**, sent to the model: each leaf is `{"value": <type> | null, "quote": string | null}`, with `additionalProperties: false` and every property required, as strict structured output needs.
- The **result schema**, which every extractor's result must match: each leaf holds `value` and at most one of `quote` (a string or null) and `locator` (a string).

`freeze` writes `.biotope/extraction/<name>/schema.yaml`: the draft plus `revision` (`sha256:` over the canonical JSON of `document`, `html_selector` and `record`), `frozen_at` and `reason`. It also writes a copy to `.biotope/extraction/<name>/revisions/<hex>.yaml`, which is never rewritten. `run` refuses a `schema.yaml` whose content no longer matches its `revision`.

**Extractor contract,** in `biotope.extraction`:

- `Document`: `path` (relative to the project root), `digest` (`sha256:` of the file), `media_type` and `text` (the stored text).
- An extractor has `name: str`, `version: str` and `settings: Mapping[str, str]`, which provenance records and which never holds a key. Its `extract(document, schema)` returns the document's records as the result schema describes.
- Biotope validates each result against the result schema, aligns the quotes and stores the records. Extractors never compute offsets.
- The `llm` extractor has `name` `llm`, a `version` that biotope raises whenever its prompt or request changes, and `settings` `model` and `endpoint` (the base URL's host name). Per document, it makes one POST with `requests` to `<endpoint>/chat/completions`, with `Authorization: Bearer <key>`, the `model`, `temperature: 0`, the schema's `document` sentence and the text, and `response_format: {"type": "json_schema", "json_schema": {"name": <name>, "strict": true, "schema": <request schema>}}`.

**Document text.** PDF: the `pypdfium2` text layer, with lines joined and U+FFFE line-end hyphen marks removed. HTML: the text of the element `html_selector` selects, or of the whole body, without scripts and styles; a selector that matches nothing fails the document. `text/plain` and `text/markdown`: read as UTF-8. Other media types are reported `unsupported` and yield no records. Texts are stored at `.biotope/extraction/texts/<hex>.txt`, named by their digest, and are never committed: biotope writes `.biotope/extraction/texts/.gitignore` containing `*`, so git ignores them in every project and biotope's `git add .biotope/` never stages them. `run` rebuilds a missing text from its document.

**Output dataset,** two JSON Lines files in `<dir>`, sorted by document path and record order:

- `documents.jsonl`, one line per extracted document: `document` (its path), `dataset` (its dataset reference), `media_type`, `provenance` and `records` (the count).
- `records.jsonl`, one line per record: `id` (`<first 16 hex of sha256 over the document path>-<n>`, counting from 1), `document`, `provenance` and `fields`. `fields` is the record with each leaf in one of four forms. A quoted leaf becomes `{"value", "quote", "start", "end", "aligned"}`, where `start` and `end` are character offsets into the stored text and both are null when `aligned` is false. A non-null value with a null quote is an unaligned leaf: `quote`, `start` and `end` null, `aligned` false. A located leaf stays `{"value", "locator"}`. A null value is stored as `{"value": null}`.
- `provenance`: `document_digest`, `text_digest` (`sha256:` of the stored text), `schema` (the name), `schema_revision`, `extractor`, `extractor_version` and `settings`.

`run` registers `<dir>` through the same code as `biotope add`, with `biotope:status` `processed` and a `prov:wasDerivedFrom` entry for each input dataset. A later run refreshes the manifest as `biotope add --rebake` does. When the manifest is curated, a run under the same schema revision as the stored output updates only the distribution's checksums and sizes. After a new schema revision, `run` leaves a curated manifest unchanged, reports that it needs review through `biotope add <dir> --bake-to …`, and exits 1.

**Reuse.** `run` reuses a document's stored records when its digest, the schema revision, the extractor, its version and its settings all equal the stored provenance. It also compares the digest of the text it makes now with the stored `text_digest`. When only that digest differs, `run` sends no request: it re-aligns the stored quotes to the new text and records the new `text_digest`.

**Report,** human and `--json`: per document, `extracted`, `reused`, `failed` with its reason, or `unsupported`; its record count; each unaligned field with record `id`, field path and quote; and the token usage the endpoint reports.

**Tests.** `pyproject.toml` registers the marker `live` and excludes it with `addopts = "-m 'not live'"`. Live tests read `OPENROUTER_API_KEY`, `HMGU_AGENTS_API_KEY`, `HMGU_AGENTS_ENDPOINT`, and `BIOTOPE_INTRAC_PAPERS`, a local directory holding InTRAC's published papers as PDF. `biotope[extract]` installs `pypdfium2` and `beautifulsoup4`.

## Acceptance criteria

Unit tests use a fake OpenAI-compatible HTTP endpoint and small committed fixtures whose text the repo authors: at least one PDF and one HTML page.

- **AC-1** (unit) `freeze` writes `schema.yaml` and the revision copy. Freezing the same content again gives the same revision and no new copy; a changed draft gives a new revision and keeps the old copy. A draft with a disallowed keyword, a property without a description, or a `record` that is not an object is refused with a reason naming the property, and nothing is written. `run` refuses a `schema.yaml` edited after freezing and names the file.
- **AC-2** (unit) In a project with the fixtures registered by `biotope add`, `run` sends one request per document that matches the Interfaces: path, bearer key from `api_key_env`, `model`, `temperature: 0`, and a strict `json_schema` with every property required and `additionalProperties: false`. The HTML text sent is that of the selected element only. The output files have the specified fields, and every aligned leaf's `text[start:end]` in the stored text matches its quote up to the differences AC-3 allows.
- **AC-3** (unit) A quote that differs from the text only in whitespace, line breaks, line-end hyphenation or case is aligned to offsets in the stored text. A quote not found keeps its value with `aligned: false`, is listed in the human and JSON reports with record `id` and field path, and the run exits 0.
- **AC-4** (unit) After `run`, `.biotope/datasets/` holds the output's manifest with `biotope:status` `processed`, a `prov:wasDerivedFrom` entry per input dataset, and record sets whose fields croissant-baker described. `biotope source generate` gives it record-set packages, as for any JSON Lines dataset. After a later run that changes the output, the manifest's checksums match the new files, also when the manifest is curated, whose curated descriptions then stay unchanged; after a new schema revision, a curated manifest stays unchanged, the report names the `--bake-to` review, and the run exits 1. In a project made by `biotope init`, git ignores every stored text and neither output file, and the index after `run` holds no stored text.
- **AC-5** (unit) A second run with unchanged documents, revision, extractor and settings sends no request and leaves both output files byte for byte the same. Changing one document re-extracts only that document. A new schema revision, extractor version, model or endpoint re-extracts every document. The records of a document removed from the input datasets leave the output. With the stored texts deleted, a run sends no request and leaves both output files the same. When the text made from an unchanged document has a digest other than the stored `text_digest`, a run sends no request, re-aligns that document's quotes so every aligned leaf's `text[start:end]` matches its quote in the new text, and records the new `text_digest`. Record IDs keep their prefix when a document's content changes, and the same file in two input datasets gives records with distinct IDs.
- **AC-6** (unit) A test module outside the `biotope` package implements the contract with locator evidence and no network. Named in `extraction.extractor`, it runs through `try` and `run` with no change to biotope: records carry its locators, provenance its name, version and settings, and switching the configuration between `llm` and it re-extracts every document.
- **AC-7** (unit) A response that fails the request schema is retried once. A second invalid response, an HTTP error, or a selector that matches nothing fails that document with its reason in the report, and the output holds none of its records. The other documents are extracted and stored, and the run exits 1.
- **AC-8** (unit) Without `extraction.model`, or with `api_key_env` naming an unset variable, `try` and `run` stop before any request with an error naming the missing key or variable. The key's value appears in no file the commands write and in none of their output, reports or error messages.
- **AC-9** (unit) `try` with a draft prints the records, evidence and alignment for the given files, and leaves every file in the project unchanged.
- **AC-10** (live) With the OpenRouter configuration, `run` extracts two papers from `BIOTOPE_INTRAC_PAPERS` and the committed HTML fixture, each under a committed schema for its kind. Every document is extracted, at least 90 % of non-null leaves are aligned, and provenance names `anthropic/claude-haiku-5.5` and `openrouter.ai`. Without the variable, the test fails with a message naming it.
- **AC-11** (live) With the HMGU configuration, `run` extracts one paper from `BIOTOPE_INTRAC_PAPERS` with the same checks as AC-10, and provenance names `qwen38`.
- **AC-12** (manual) Vlad reads `skills/biotope-croissant` and confirms: documents go through extraction; the agent proposes each extraction schema from `biotope map --show` (purpose, entities, relations) and sample documents, and shows the user `biotope extract try` output; the agent runs `freeze` only after the user approves the schema and quotes that approval in `--reason`; only public documents go to an external model; and this fits the skill's ownership rule.
- **AC-13** (manual) With schemas an agent proposed and Vlad froze, `run` extracts InTRAC's six papers, at least three CHC profile pages and two or three ERC calls. Vlad judges the values against the documents.

## Freedom to operate

The implementer decides the module layout, the prompt wording, text normalization beyond AC-3, request timeouts, the order and concurrency of requests, how `try` presents records, the wording of reasons, and how the registration reuses `biotope add`'s code.

## Design sketch (non-binding)

- A package `biotope/extraction/` (schema and wire schema, text, alignment, `llm`, run) and `biotope/commands/extract.py`. The `requests` and `pydantic` dependencies already exist.
- Alignment normalizes text and quote while keeping, for every kept character, its index in the original; it searches the normalized quote, then maps the match back. The first occurrence wins.
- Reuse compares each document's provenance in `documents.jsonl` with the current one, so the stored output is also the cache.
- `_document_hint` in `biotope/graph/render.py` names `biotope extract` as the route for a document, and `skills/biotope-croissant/references/curation.md` follows.
- Give requests a generous timeout: `qwen38` took up to 32 s per paper in the research trial.

## Risks and open questions

- Croissant-baker's description of nested JSON Lines may be verbose for mapping authors. If it is unusable, the implementer reports it before flattening the output, which would change the Interfaces.
- Stored texts are ignored and rebuilt from the documents, so a clone without the documents can read the records but cannot check their offsets.
- A paper longer than the model's context fails as a document with the endpoint's error. Claude's tokenizer counts about 1.5 times Qwen's on the same paper.

## Evidence required in the PR

- The unit and live test output, with the OpenRouter spend of the live run, which stays under 1 USD.
- For AC-13: the frozen revisions, the run report (records, aligned share, failures) and Vlad's verdict.
- `uv run mkdocs build --strict` passing with `docs/extraction.md` in both nav files.
