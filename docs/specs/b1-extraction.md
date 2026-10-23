# B1: Extraction

Needs: none · Roadmap decisions: 1–8, 14 · Research: [`docs/research/b1-extraction.md`](../research/b1-extraction.md)

## Goal and why

After B1, a project turns local documents (PDF, HTML, plain text) into stored, versioned structured records under an extraction schema a person reviewed. Every value carries its evidence, and every record names its document, the schema revision and the extractor that produced it. The result is a dataset that enters `biotope add` and the existing machinery like any structured file.

Today a document becomes a source whose facts an agent transcribes by hand, with no checkable link between a value and the text it came from. That does not scale to REACH's CHC profile pages and ERC calls or to InTRAC's papers, the three kinds of document B1 is tested on.

The milestone respects these roadmap decisions:

- 1: biotope is never a fetcher or scraper; documents are local files.
- 2: extraction is a stage before `add`; its output is a derived dataset (`prov:wasDerivedFrom`, status `processed`), and `graph build` stays deterministic and offline.
- 3: the extractor is swappable behind a contract; the first calls an LLM, a later one applies rules an agent writes.
- 4: extraction is stored and reproducible, and repeats only when its inputs change.
- 5: the LLM extractor calls an OpenAI-compatible API; the key always comes from an environment variable, and biotope has no default model.
- 6 and 14: only public documents go to an external model, and tests use only public material.
- 7: people review artefacts, not records; an agent proposes the extraction schema and a person approves it.

## Scope

- Extraction schemas written as typed Python classes in the project, like the topology, and checked by pyright with the rest of the project.
- The extractor contract and the built-in LLM extractor.
- Commands to try a schema on sample documents and to run extraction over registered datasets.
- Evidence for every value, record IDs that survive re-extraction, reuse of stored results, and registration of the output as a processed, derived dataset.
- The `biotope-croissant` skill: the agent proposes each extraction schema from the project's purpose and sample documents, shows the user trial output, and runs the full extraction only after the user approves the schema.

## Non-goals

- The rule-based extractor. B1 has only a test extractor standing in for it.
- Layout-aware table recovery, such as row and column locators. It comes later as an extractor capability behind the same contract. InTRAC's competence questions need no value that exists only in a table inside a paper (checked on 23 October 2026: all 30 cite only InTRAC's CSV and spreadsheet files).
- OCR and scanned PDFs.
- Evaluation: gold sets, precision and recall, model comparisons.
- Fetching or scraping; internal or confidential documents (decision 6).
- Identity and precedence across records and documents (B2); the ID registry, human decisions and release history (B3).
- Editing an extracted dataset's description by hand. Biotope writes it from the schema.

## Interfaces

**Commands.** Biotope runs from the data project's folder. `biotope extract try` runs the configured extractor with a schema on given files and shows the records with their evidence, changing nothing in the project. `biotope extract run` extracts the documents of registered datasets under one schema, stores the records and registers them. Both have human and `--json` output, as `CONTRIBUTING.md` describes. A run reports, per document, whether it was extracted, reused or failed with its reason; the unaligned values; and the record IDs that disappeared and appeared since the stored result. It exits nonzero when a document failed. `graph check`, `quality` and `build` never call an extractor.

**Extraction schema.** A typed Python class per kind of document, with a docstring and a description per field, as the topology's concepts have. Biotope derives the model-facing JSON Schema from it with pydantic, and rejects, naming the field, any construct that strict structured output cannot express. The schema's **revision** is the digest of that derived JSON Schema. The schema lives in git like other project code; there is no freeze step and no revision copy. A schema may declare its **record key**, the fields that identify a record within its document. A schema without a key yields at most one record per document.

**Extractor contract.** An extractor declares its name and version, and the settings provenance records, never a key. Given one document and a schema, it returns the document's records, in which each non-null value carries a quote from the document or a locator. Biotope validates the result against the schema and aligns the quotes; an extractor never computes positions. The rule-based extractor will plug in here, and so will table recovery. A project selects the built-in LLM extractor or its own by configuration, without changing biotope.

**Extracted output,** what later stages may rely on:

- Records with an `id`, their document, their provenance and their fields. The output is committed with the project. The document texts biotope makes for alignment are never committed, since they can hold copyrighted full text, and are regenerable from the documents.
- **Record IDs** are derived from the document's path and the record key's values, never from a record's position, so re-extraction keeps an ID while its key values stay the same. Without a key, the document's path alone gives the ID. Two records of one document with the same key values are reported.
- **Evidence.** Each value carries its quote, aligned by biotope to the document's text, and where it is in the document, at least the page for a PDF. A value read from a table quotes the table's whole row, with its page. A value whose quote cannot be aligned is kept, marked unaligned and reported. A value from a locator-based extractor carries its locator.
- **Provenance** per record: the document's path and digest, the schema name and revision, and the extractor's name, version, model and endpoint.
- The output is registered as a dataset with status `processed` and `prov:wasDerivedFrom` its input datasets. Its Croissant field descriptions come from the schema, and every run that changes the output refreshes them.
- **Re-extraction** happens only when a document, the schema revision or the extractor (name, version, model, endpoint) changes; otherwise stored results are reused.

**The chain to B2 and B3.** An extracted record ID names the same record across re-extraction, and the run's report of disappeared and appeared IDs keeps changes visible. B2 uses these IDs and the records' fields to decide which records are one entity. B3's registry gives entities their persistent IDs; an extracted record ID becomes one of an entity's aliases, next to emails and ORCIDs. B1 mints no entity IDs.

**Project configuration,** in `.biotope/config.yaml`: the extractor; for the LLM extractor, the endpoint URL (which may be written literally), the name of the environment variable holding the key, and the model. Biotope has no default model. REACH and InTRAC use `deepseek/deepseek-v4.1-flash` through OpenRouter with `OPENROUTER_API_KEY`, and so do biotope's live tests.

## Acceptance criteria

Unit tests use a fake OpenAI-compatible endpoint and small public fixtures the repo authors, at least one PDF and one HTML page.

- **AC-1** (unit) A schema class gives the same revision on every derivation and a new one when a field or description changes. A construct strict structured output cannot express is refused with a reason naming the field, before any request is sent.
- **AC-2** (unit) `run` over the registered fixtures stores records whose IDs, documents, provenance and evidence match the Interfaces. Every aligned quote is found in its document's text, PDF values name their page, and an unalignable quote keeps its value and appears in the report without failing the run.
- **AC-3** (unit) The output is registered as a processed dataset derived from its inputs, with field descriptions taken from the schema, and `biotope source generate` handles it like any other structured dataset. In a project made by `biotope init`, git tracks the extracted records and ignores every document text.
- **AC-4** (unit) A second run with nothing changed sends no request and leaves the output unchanged, also when the document texts were deleted. Changing one document re-extracts only that document. A new schema revision, extractor version, model or endpoint re-extracts every document.
- **AC-5** (unit) When re-extraction returns the same key values in another order, every record keeps its ID. When key values change, the report lists the IDs that disappeared and appeared. A schema without a key gives each document one ID from its path. Duplicate key values within one document are reported.
- **AC-6** (unit) A test extractor outside the `biotope` package, returning locator evidence without network, runs through `try` and `run` when the configuration names it, with no change to biotope. Its records carry its locators, and their provenance its name and version.
- **AC-7** (unit) A document whose extraction fails is reported with its reason, the other documents are stored, and the run exits nonzero.
- **AC-8** (unit) Without a model, or with a key variable that is unset, `try` and `run` stop before any request and name what is missing. The key's value appears in no file biotope writes and in none of its output.
- **AC-9** (unit) `try` shows the records and evidence for the given files and leaves every file in the project unchanged.
- **AC-10** (live) With `deepseek/deepseek-v4.1-flash` through OpenRouter and `OPENROUTER_API_KEY` from the environment, `run` extracts biotope's small public fixtures, including a PDF with a table. Every document is extracted, at least 90 % of non-null values are aligned, a value from the table quotes its row with its page, and the run costs under 0.10 USD.
- **AC-11** (manual) Vlad reads the `biotope-croissant` skill and confirms: documents go through extraction; the agent proposes each schema from the project's purpose and sample documents and shows the user `try` output; the full run waits for the user's approval; only public documents go to an external model; and this fits the skill's ownership rule.
- **AC-12** (manual) In data projects, with schemas an agent proposed and Vlad approved, extraction runs on InTRAC's six published papers (in `scratch/intrac_test/`), at least three CHC profile pages and two or three ERC calls (on a dev branch of slolab/reach). Vlad judges the values and their evidence against the documents.

## Freedom to operate

The implementer decides everything the Interfaces leave open, including: command options and how `try` presents records; the output's files, layout and format, as long as croissant-baker describes it and mappings can read values with their evidence; how a schema declares its key; the prompt and request; document-to-text conversion, any HTML content selection, and normalization; the alignment method and the locator format; retries, timeouts and concurrency; the configuration's key names; and the report's wording and fields beyond those named.

## Design sketch (non-binding)

- The research note's choices: strict `json_schema` output over `requests`, `pypdfium2` for PDF text, the standard library or BeautifulSoup for HTML, and biotope's own quote alignment instead of LangExtract.
- `_document_hint` in `biotope/graph/render.py` and the skill's `references/curation.md` should point documents to `biotope extract`.

## Risks and open questions

- `deepseek/deepseek-v4.1-flash` was not in the research trial, so its quote fidelity on these documents is unmeasured until AC-10.
- Croissant-baker's description of nested records may be hard for mapping authors to read; if so, the implementer reports it before choosing a flatter output.
- A clone without the documents can read the records but cannot re-check their quotes.

## Evidence required in the PR

- Unit and live test output, with the OpenRouter spend of the live run.
- For AC-12: the approved schemas, the run reports and Vlad's verdict.
- `uv run mkdocs build --strict` passing.
