# B1: Extraction

Needs: none · Roadmap decisions: 1–4 · Research: [`docs/research/b1-extraction.md`](../research/b1-extraction.md)

## Goal and why

After B1, a project turns local documents (PDF, HTML, plain text) into stored, versioned structured records under an extraction schema a person reviewed. Every value carries its evidence, and every record names its document, the schema revision and the extractor that produced it. The result is a dataset that enters `biotope add` and the existing machinery like any structured file.

Today a document becomes a source whose facts an agent transcribes by hand, with no checkable link between a value and the text it came from. That does not scale to REACH's CHC profile pages and ERC calls or to InTRAC's papers, the three kinds of document B1 is tested on.

The milestone respects these rules:

- biotope is never a fetcher or scraper; documents are local files.
- extraction is a stage before `add`; its output is a derived dataset (`prov:wasDerivedFrom`, status `processed`), and `graph build` stays deterministic and offline.
- the extractor is swappable behind a contract; the first calls an LLM, a later one applies rules an agent writes.
- extraction is stored and reproducible, and repeats only when its inputs change.
- the LLM extractor calls an OpenAI-compatible API; the key always comes from an environment variable, and biotope has no default model.
- only public documents go to an external model (roadmap decision 3), and tests use only public material.
- people review artefacts, not records; an agent proposes the extraction schema and a person approves it.

## Scope

- Extraction schemas written as typed Python classes in the project, like the topology. Biotope derives the model-facing JSON Schema from a class, refuses any construct that strict structured output cannot express, naming the field, and takes the digest of the derived JSON Schema as the schema's revision. There is no freeze step.
- The extractor contract and the built-in LLM extractor. The project's configuration selects the extractor and, for the LLM extractor, the endpoint URL, the name of the environment variable that holds the key, and the model. REACH, InTRAC and biotope's live tests use `deepseek/deepseek-v4.1-flash` through OpenRouter with `OPENROUTER_API_KEY`.
- Two commands, run from the data project's folder. `biotope extract try` runs the configured extractor with a schema on given files and shows the records with their evidence, changing nothing in the project. `biotope extract run` extracts the documents of registered datasets under one schema, stores the records and registers them as a dataset with status `processed`, `prov:wasDerivedFrom` its input datasets and field descriptions from the schema. `graph check`, `quality` and `build` never call an extractor.
- A run report: per document, whether it was extracted, reused, failed or missing, with the reason; the unaligned values; the record IDs that disappeared and appeared; and each old ID with its new one for documents that moved. The run exits nonzero when a document failed or is missing.
- The `biotope-croissant` skill: the agent proposes each extraction schema from the project's purpose and sample documents, shows the user `try` output, and runs the full extraction only after the user approves the schema.

## Non-goals

- The rule-based extractor; B1 has only a test extractor standing in for it.
- Layout-aware table recovery, such as row and column locators. It comes later behind the same contract. InTRAC's competence questions need no value that exists only in a table inside a paper (checked on 23 October 2026: all 30 cite only InTRAC's CSV and spreadsheet files).
- OCR and scanned PDFs; evaluation (gold sets, precision and recall, model comparisons); fetching or scraping; internal or confidential documents (roadmap decision 3).
- Identity and precedence across records and documents, the ID registry and human decisions, which are project code (roadmap decision 2), and release history.
- Editing an extracted dataset's description by hand. Biotope writes it from the schema.

## Interfaces

**Extractor.** A Python protocol that projects may implement. An extractor declares its name, its version and its non-secret settings, such as the model and the endpoint, never a key. It receives one document as biotope's converted text, with the document's path, digest and media type, and the extraction schema. It returns that document's records, in which each non-null value carries its evidence: a quote from the given text or a locator. Biotope validates the records against the schema and aligns the quotes; an extractor never computes positions. A project selects the built-in extractor or its own by configuration, without changing biotope. The rule-based extractor and table recovery will plug in here.

**Record key.** A schema may declare its record key, the fields that identify a record within its document. A schema without a key yields at most one record per document.

**Stored output,** what later stages may rely on:

- One record per line, each with its ID, its document, its values with their evidence, and its provenance. The records are committed with the project. The document texts biotope makes are never committed, since they can hold copyrighted full text, and can be made again from the documents.
- **Record IDs** come from the document's path and the record key's values, never from a record's position, so re-extraction keeps an ID while its key values stay the same. Without a key, the path alone gives the ID. Two records of one document with equal key values, both null included, fail that document. A project's alignment code uses these IDs to decide which records are one entity, and a project's key map may keep them as aliases of its permanent IDs (roadmap decision 2); B1 mints no entity IDs.
- **Evidence.** A quote is aligned by biotope to the document's text and says where it is, at least the page for a PDF. A value read from a table quotes the table's whole row, with its page. A value whose quote cannot be aligned is kept, marked unaligned and reported. A value from a locator-based extractor carries its locator.
- **Provenance** per record: the document's path and digest, the schema name and revision, and the extractor's name, version and settings.
- **Reuse.** A document is extracted again only when its digest, the schema revision, or the extractor's name, version or settings change. Otherwise its stored records are reused without a model call, also after the document moved; its record IDs then follow the new path. A registered document whose file is missing keeps its stored records, so a clone without the documents still builds. A document removed from its dataset loses its records.

## Acceptance criteria

Unit tests use a fake OpenAI-compatible endpoint and small public fixtures the repo authors, at least one PDF and one HTML page.

- **AC-1** (unit) A schema class gives the same revision on every derivation and a new one when a field or description changes. A construct strict structured output cannot express is refused with a reason naming the field, before any request is sent.
- **AC-2** (unit) `run` over the registered fixtures stores records whose IDs, documents, provenance and evidence match the Interfaces. Every aligned quote is found in its document's text, PDF values name their page, and an unalignable quote keeps its value and appears in the report without failing the run.
- **AC-3** (unit) The output is registered as a processed dataset derived from its inputs, with field descriptions taken from the schema, and `biotope source generate` handles it like any other structured dataset. In a project made by `biotope init`, git tracks the extracted records and ignores every document text.
- **AC-4** (unit) A second run with nothing changed sends no request and leaves the output unchanged, also when the document texts were deleted. Changing one document re-extracts only that document. A new schema revision, extractor version or extractor setting, such as the model or endpoint, re-extracts every document. After `biotope mv` moves a dataset, a run sends no request, the record IDs follow the new paths, and the report lists each old ID with its new one.
- **AC-5** (unit) When re-extraction returns the same key values in another order, every record keeps its ID. When key values change, the report lists the IDs that disappeared and appeared. A schema without a key gives each document one ID from its path. Two records of one document with equal key values, both null included, fail that document as in AC-7.
- **AC-6** (unit) A test extractor outside the `biotope` package, returning locator evidence without network, runs through `try` and `run` when the configuration names it, with no change to biotope. Its records carry its locators, and their provenance its name, version and settings.
- **AC-7** (unit) A document whose extraction fails is reported with its reason, the other documents are stored, and the run exits nonzero. A registered document whose file is missing is reported as missing, its stored records are kept, and the run exits nonzero. A document removed from its dataset loses its records, and the report lists their IDs as disappeared.
- **AC-8** (unit) Without a model, or with a key variable that is unset, `try` and `run` stop before any request and name what is missing. The key's value appears in no file biotope writes and in none of its output.
- **AC-9** (unit) `try` shows the records and evidence for the given files and leaves every file in the project unchanged.
- **AC-10** (live) With `deepseek/deepseek-v4.1-flash` through OpenRouter and `OPENROUTER_API_KEY` from the environment, `run` extracts biotope's small public fixtures, including a PDF with a table. Every document is extracted, at least 90 % of non-null values are aligned, and a value from the table quotes its row with its page.
- **AC-11** (manual) Vlad reads the `biotope-croissant` skill and confirms: documents go through extraction; the agent proposes each schema from the project's purpose and sample documents and shows the user `try` output; the full run waits for the user's approval; only public documents go to an external model; and this fits the skill's ownership rule.
- **AC-12** (manual) With schemas an agent proposed and Vlad approved, extraction runs on InTRAC's six published papers, in a biotope project initialized at `/home/vladsam42/Projects/biotope_project/scratch/intrac_test/` (the papers are under `intrac_260909/data/papers/`), and on at least three CHC profile pages and two or three ERC calls, on a dev branch of slolab/reach. Vlad judges the values and their evidence against the documents.

## Freedom to operate

The implementer decides everything the Interfaces leave open, and documents in `docs/` what projects write or read: the configuration's key names, the extractor protocol's signature, how a schema declares its key, and the output's files, layout and format, as long as croissant-baker describes it and mappings can read values with their evidence. The implementer also decides command options and how `try` presents records; the prompt and request; document-to-text conversion, any HTML content selection, and normalization; the alignment method and the locator format; retries, timeouts and concurrency; and the report's wording and fields beyond those named.

## Design sketch (non-binding)

The research note's choices: strict `json_schema` output over `requests`, `pypdfium2` for PDF text, the standard library or BeautifulSoup for HTML, and biotope's own quote alignment instead of LangExtract. `_document_hint` in `biotope/graph/render.py` and the skill's `references/curation.md` should point documents to `biotope extract`.

## Risks and open questions

- `deepseek/deepseek-v4.1-flash` was not in the research trial, so its quote fidelity on these documents is unmeasured until AC-10.
- Croissant-baker's description of nested records may be hard for mapping authors to read; if so, the implementer reports it before choosing a flatter output.
- A clone without the documents can build from the records but cannot re-check their quotes.

## Evidence required in the PR

- Unit and live test output, with the OpenRouter spend of the live run, which stays under 0.10 USD.
- The `docs/` pages for the configuration keys, the extractor protocol, the record key and the output format.
- For AC-12: the approved schemas, the run reports and Vlad's verdict.
- `uv run mkdocs build --strict` passing.
