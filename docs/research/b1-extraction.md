# B1 extraction: tools and model

Research for milestone B1 (roadmap decisions 2 to 6), done on 22 October 2026. It answers two questions before the spec: which maintained tools to adopt for extraction and document conversion, and which model to use on each OpenAI-compatible provider. Package versions, dependency counts (packages resolved by `uv pip compile` for Python 3.12, the package included) and prices are from that day.

## Tools for LLM extraction

- **OpenAI structured outputs (`response_format` with a strict `json_schema`): adopt.** It is the API itself, so it works on any OpenAI-compatible endpoint that supports it. All six models tried, on OpenRouter and the HMGU endpoint, returned valid JSON with exactly the schema's keys on every document. The extraction schema becomes a JSON Schema (pydantic can generate it); strict mode needs `additionalProperties: false` and every property required. It gives no evidence by itself: evidence is a field of the schema (a `quote` beside each `value`), checked by biotope.
- **Call the API with `requests`, not the `openai` SDK.** One extraction is one POST to `/chat/completions`. `requests` and `pydantic` are already biotope dependencies; `openai` 3.36 adds 14 packages for nothing biotope needs.
- **Google LangExtract 1.7.1: do not adopt, borrow its idea.** It is maintained (Apache-2.0, released 8 October 2026), supports OpenAI-compatible endpoints through `provider_kwargs` with `base_url`, and is the only candidate with source grounding: it aligns every extraction to character offsets (`char_interval`) and leaves it empty when the text cannot be found. Against it: 57 packages, including `google-genai`, `google-cloud-storage`, pandas and aiohttp; its data model is a flat list of extractions (class, text, attributes), not a nested reviewed schema; it is tuned around few-shot examples. Its grounding is the part B1 needs, and it is about twenty lines in biotope: find each quote in the stored text, exactly and then ignoring whitespace and hyphenation, and record its offsets or flag the field.
- **instructor 1.17: do not adopt.** MIT, maintained, 41 packages. It adds pydantic validation with re-asking and per-provider modes (`TOOLS`, `JSON`, `TOOLS_STRICT`, `MD_JSON`), but no grounding. Strict `json_schema` already gives valid output on both providers, so the only remaining value is retry on a failed check, which is one loop in the extractor. Its provider modes would also become a second place where provider differences live.
- **outlines 1.3: do not adopt.** Apache-2.0, 18 packages. Its value is constrained decoding for models run in-process; through an OpenAI-compatible API it forwards the schema the provider already enforces. No grounding.
- **Swappability.** None of these is needed to keep the extractor swappable. The contract (documents plus frozen schema in, records with per-field evidence out, name and version declared) is biotope's own; the LLM extractor is one implementation that builds a prompt, sends the schema, and grounds the quotes.

## Tools for document-to-text conversion

Evidence must point into a text that biotope stores and hashes, so conversion should be deterministic, fast and lossless rather than clever. The stored text, not the PDF or HTML, is what quote offsets refer to.

- **PDF: adopt `pypdfium2` 5.14.** BSD-3/Apache-2.0, no dependencies, pdfium's text layer. On the six InTRAC papers it took 0.02 to 1.3 s per paper and produced no ligature characters. It breaks lines mid-sentence and marks line-end hyphens with U+FFFE, so a small normalization joins lines; the hyphen cannot always be told apart from a real one ("single-nucleus"), which is why quote matching ignores hyphens.
- **`pypdf` 6.21: second choice.** BSD-3, pure Python, no dependencies, but slower (0.9 s on a 16-page paper) and it left 237 ligature characters and 189 hyphenated line breaks in that paper.
- **`pymupdf4llm` 2.0: do not adopt.** Good Markdown with paragraphs and tables, but PyMuPDF is AGPL-3.0 (or commercial), which does not fit biotope's Apache-2.0 distribution, PyMuPDF 2.0 now pulls `onnxruntime`, numpy and networkx (12 packages), and it took 5.8 s against pdfium's 0.1 s on the same paper.
- **docling 2.141 and marker-pdf 2.0: do not adopt now.** Maintained and strong on layout, tables and scans, but 122 and 101 packages with ML models. Published papers have a text layer. If scanned documents or table-heavy sources arrive, either can sit behind the same conversion step later as an optional extra.
- **HTML: do not adopt trafilatura 2.3.** Apache-2.0, 18 packages, maintained. On the CHC profile of Hannah Spitzer it kept 2.8k characters but dropped the career dates ("Since 2023", "2019 - 2023"), the Impact statement and the publication list, which are fields REACH wants. Boilerplate removal is a guess biotope cannot review.
- **HTML: use the standard library's `html.parser`, or BeautifulSoup (3 packages) if selectors are wanted,** with an optional content selector the project declares (for the CHC site, `main`). The profile's `main` element gives 7.9k characters with everything above; the whole page gives 15.9k. Both fit any candidate model's context.
- **markitdown 0.1.9: do not adopt.** MIT, 26 packages with its PDF extra, and no gain over the two choices above.

## Trial setup

- Documents, all public: the CHC profile of Hannah Spitzer (helmholtz-munich.de/en/icb/hannah-spitzer, trafilatura text, about 0.7k tokens), the ERC Advanced Grant page (erc.europa.eu/apply-grant/advanced-grant, about 2.3k tokens), and two InTRAC papers converted with pypdfium2: Hill et al. 2024, Nat Commun, ATRNL1 in atrial fibrillation (about 26k tokens), and Garlapati et al. 2024, Circ Res, macrophage factor VII (about 18k tokens).
- Schemas: person (name, group, research topics, methods), call (name, eligibility, funding, duration, deadlines), paper (title, organisms, tissues, cell types, comparisons). Every value is an object with `value` and `quote`, sent as a strict `json_schema`. The system prompt asks for quotes copied character for character. Temperature 0, one call per document, no retries, no examples.
- Measures: valid JSON with the schema's keys; quotes found exactly in the text sent; quotes found ignoring whitespace, hyphens and case; latency; cost reported by OpenRouter.
- Models: HMGU `qwen38`, `flashnext` and `gemma4-12b` (free to us); OpenRouter `anthropic/claude-haiku-5.5` and `openai/gpt-6-luna` (both 0.10 USD per million input tokens, 0.50 output) and `anthropic/claude-sonnet-5.5` (2 and 10 USD).
- The HMGU endpoint lists four models: `gemma4-12b` (32k context), `qwen38` (131k), `flashnext` (65k) and `qwen38-code` (131k). `qwen38` and `flashnext` count the same tokens, so they share a Qwen tokenizer.

## Trial results

Every model returned valid, schema-shaped JSON on all four documents. Verbatim quotes, exact match, over the four documents:

- claude-haiku-5.5: 50 of 51 (98 %), 5 to 7 s per document, 0.009 USD for all four (0.004 for the longer paper).
- claude-sonnet-5.5: 58 of 59 (98 %), 5 to 8 s, 0.178 USD for all four (0.085 for the longer paper).
- qwen38: 66 of 68 (97 %), 7 to 32 s.
- gpt-6-luna: 65 of 68 (96 %), 10 to 29 s, 0.008 USD for all four.
- flashnext: 47 of 49 (96 %), 7 to 13 s, with thinking turned off.
- gemma4-12b: 51 of 56 (91 %), 9 to 21 s.

Ignoring whitespace and hyphens changed little (one extra match each for luna and gemma). Every miss was a stitched or lightly reworded span, such as two sentences joined with "...", never invented text, except that gemma replaced "MΦs" with "MϦs" in four quotes. A grounding check catches all of them.

Value quality differed more than quote fidelity. Haiku and Sonnet named the study's own organisms, tissues and comparisons. Luna was equally correct but wrote descriptive phrases rather than terms. qwen38 and gemma over-extracted mentions as study subjects: mouse from "ATRNL1 knockout mice have no such phenotype", brain and testis from an isoform remark, humans in the mouse study. flashnext was precise but incomplete (only "AF vs control", no left ventricle). Part of this is the schema's field descriptions, which a reviewed schema should tighten ("organisms whose samples the study analysed").

Operational findings on the HMGU endpoint:

- `flashnext` reasons by default, and non-streamed requests that ran longer than about a minute failed with "Connection error"; with `chat_template_kwargs: {"enable_thinking": false}` every request finished in under 13 s. The extractor should either disable thinking or stream.
- `gemma4-12b`'s 32k context is too small for three of the six InTRAC papers (pdfium text of about 39k, 46k and 32k tokens). `flashnext` fits all six; `qwen38` fits all six with room for supplements.
- Claude's tokenizer counts about 1.5 times as many tokens on the same paper as Qwen's (38.7k against 25.8k), which the cost estimate below includes.

Total spent: 0.195 USD on OpenRouter; the HMGU endpoint is free to us.

## Recommended models

- **OpenRouter: `anthropic/claude-haiku-5.5`.** Highest quote fidelity (tied with Sonnet), fastest, precise values, about 0.004 USD per full paper, so B1's whole test set (six papers, the CHC pages, a few calls) costs a few cents per run. Keep `anthropic/claude-sonnet-5.5` as the reference when reviewing a new extraction schema or judging a disputed record: same fidelity, slightly richer values, twenty times the price.
- **HMGU: `qwen38`.** 131k context fits every paper, strict schemas work, 97 % exact quotes, best recall of the three. Its weakness is over-extraction, which tighter field descriptions and review address. `flashnext`, with thinking off, is the faster alternative when precision matters more than recall. Do not use `gemma4-12b` for papers.
- Since decision 6 limits this version to public documents, the provider choice is about cost and quality, not data protection. The model id, endpoint and provider are part of each record's provenance (decision 4), so switching later only re-extracts.

The trial's scripts and outputs are not in the repo; they were throwaway smoke-test code.

## Decision

On 23 October 2026 Vlad chose `deepseek/deepseek-v4.1-flash` on OpenRouter for B1's tests and runs, instead of the models recommended above. It was not trialled in this research. OpenRouter lists it that day with a 1M-token context, strict structured output, and 0.165 USD per million input tokens and 0.66 per million output tokens. B1's live test (AC-10) is the first measure of its quote fidelity.
