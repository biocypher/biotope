# Roadmap: data products

Biotope 0.10 builds a typed knowledge graph from local structured files in one pure pass. The next version makes biotope a reusable framework for building and maintaining a **data product**: a versioned representation of a domain, built from local sources of any kind, structured or not, and kept current as data and needs change.

REACH, the Computational Health Center's register of who works on what ([slolab/reach](https://github.com/slolab/reach)), is the testing ground. InTRAC, with its published papers, is the second user, and the ELIXIR Atlas is expected to be the third. A feature belongs in biotope only if it makes sense beyond REACH.

This roadmap records the premises and decisions from the alignment of 22 October 2026, revised on 26 October 2026 after the first B2 and B3 specs rebuilt inside biotope what 0.10 already provides. Each milestone gets a spec in `docs/specs/` and one PR.

## Terms

- **Data product:** the versioned output of a biotope project, a release of typed records with provenance. The BioCypher graph and SQLite are exports of a release.
- **Unstructured source:** a local document whose content has no record structure, such as an HTML page, a PDF or a grant call. Croissant-baker describes it as a bare file.
- **Extraction:** the stage that turns unstructured sources into structured records under a reviewed extraction schema. Its output is an ordinary structured source.
- **Extraction schema:** the fields extraction fills for one kind of document. It is not the topology: the mapping from extracted records to topology objects is ordinary mapping.
- **Extractor:** a swappable implementation of extraction. The first calls an LLM; a later one applies rules an agent writes.
- **Release:** one build of a project whose run record the project commits. The run record names the build's exact inputs and code; git over the run records is the release history.
- **Human decision:** a person's judgement on a record, such as accepting or rejecting a match, overriding a field or excluding a link. It is an input dataset that the project's alignment and mappings apply.

## What 0.10 already provides

Read this before proposing a milestone. The first B2 and B3 specs missed it and were withdrawn.

- **Harmonization.** `graph/standardization.py` holds the terms that fields of several sources bind to; each source schema declares its own aliases and missing-value tokens, and its loader applies them.
- **Identity.** `graph/alignment/` is the project's stage for cross-source identity, run before any mapping. The project owns identities; biotope supplies contracts for recording and checking those decisions ([architecture](architecture.md)). Every `SourceRecord` carries its evidence, and every exported object points into `provenance.json`.
- **Conflicts and source priority.** The runtime refuses two different objects with one ID and asks the project to resolve the conflict in its pipeline. Which source wins for a field is decided there, in alignment or mappings.
- **Inputs and code.** Croissant gives every described file its sha256. `run.json` records each source's manifest digest, contract digest and file list with those hashes, the code digests and `graph_digest`. Contract revisions in `.biotope/contracts/` let `graph check` report source drift. `biotope check-data` compares files with their recorded sha256, as a separate command. `graph build --out` writes a build to any directory.

## Rule for new milestones

Vlad, 26 October 2026: "Don't make this mistake again and always double check by stepping back and considering the project as a whole, as well as exploring thoroughly what already exists and why." Before a spec is written, its author maps what biotope already does for the need and why it was built that way, verified in code, and names the gap in one sentence. The spec opens with that sentence.

## Lifecycle

```text
local documents ── extraction ── extracted records ─┐
                                                    ├─ croissant-baker ── reviewed sources
local structured files ─────────────────────────────┘                          │
                                                                               ▼
project registry and decisions ─────────► project alignment and mappings ──► build ──► committed run record
                                                                               │
                                                               graph, SQLite, project apps
```

A **new project** starts from raw data and its purpose. An agent proposes the extraction schemas, the topology, the alignment and the mappings, and a person reviews them.

An **evolving project** meets two kinds of change. New rows in a known source need the file described again and a rebuild. A new kind of source, or a new need, may change the topology; that change is reviewed, and the project's alignment carries existing IDs and human decisions across it. Biotope tells the user or agent what changed and what must be reviewed.

## Decisions

1. **Biotope's scope.** Biotope owns the representation of the data and its mapping: extraction, sources, topology, the contracts that record and check a project's identity and precedence decisions, and releases. It is never a fetcher or scraper, a scheduler, an application layer (search, user interfaces, writing back to tools such as Airtable), a general ETL tool, or a judge of equivalence. Downloading a source is a script the project adds.
2. **Extraction is a stage before `add`.** A raw document goes through an extractor into a stored, derived dataset (`prov:wasDerivedFrom`, status `processed`). Croissant-baker then describes it like any other file. `graph build` stays deterministic and offline.
3. **The extractor contract.** An extractor takes documents and a reviewed extraction schema, and returns records that match the schema. Each record points to its document and each field carries its evidence, the quoted span or a locator. An extractor declares its name and version. Whether it uses an agent or generated rules is hidden behind the contract.
4. **Extraction is stored and reproducible.** Extracted records are versioned with their provenance: document hash, schema revision, extractor name and version, model and endpoint. A document is extracted again only when one of these changes.
5. **The LLM extractor calls an OpenAI-compatible API.** OpenRouter and the HMGU endpoint both serve one. The endpoint URL is project configuration and may be written literally, since it is not a secret. The key always comes from an environment variable that the configuration names. The model is chosen after research, not by default.
6. **Public inputs only in this version.** Only public documents go to an external model: public HTML pages, public ERC calls and InTRAC's published papers. Internal sources, such as presentations and contracts, come later and will need a per-source policy.
7. **People review artefacts, not records.** An agent proposes the extraction schemas, the topology and the mapping priorities and conflict resolution from the project's purpose, and a person reviews them. The rest follows the `biotope-croissant` skill: the user owns scientific decisions, the agent engineering ones, and the agent stops and asks before merging identities without a shared accession.
8. **Builds are pure.** A build is a function of its inputs and the project's committed files, and biotope keeps no hidden state. Human decisions are an input dataset like any other source, and each project chooses whether to commit it: REACH reads Anna's from Airtable at each build, so names and emails stay out of git (Vlad, 23 October 2026: "ok" to "decisions such as Anna's corrections are an input dataset").
9. **Identity and source priority are project code.** As 0.10 designs it, the project resolves cross-source identity in `graph/alignment/` before mappings run, and decides which source wins for a field in alignment or mappings. Biotope records and checks those decisions through evidence, provenance, contract revisions and the run record. It adds no declaration language for keys or precedence and no merging of its own.
10. **Stable IDs and human decisions live in the project.** Entities with natural keys, such as genes and DOIs, keep them. A project whose IDs are pointed at from outside, as REACH's are from Airtable rows and search, keeps its own registry of IDs and applies its human decisions (match decisions, overrides, link edits) in its alignment and mappings. For REACH, the registry and Anna's corrections, with the rules REACH already applies to them, live in REACH's biotope project.
11. **Generic pieces only on evidence.** Biotope adds a generic piece for identity, decisions or state only when a second project needs the same piece, or when REACH pass 1 shows a gap that project code cannot fill. Each such piece follows the rule for new milestones.
12. **Releases: checked inputs, history in git.** A release records its exact inputs through what Croissant already holds, each file's sha256, and the build refuses an input file that no longer matches its description. The run record holds no record values, so a project can commit it, and git over the run records is the release history. Biotope diffs two builds by object ID. A past release can be rebuilt from its inputs and committed files while the project keeps those input files; biotope stores no raw snapshots (Vlad, 23 October 2026: "wouldn't it be too much? And doesn't croissant already do that? Let's not overbuild this part, reuse existing tools if possible").
13. **Breaking 0.10 is allowed.** Biotope is before 1.0. Each break gets a note in `migration.md`. biotope-bench is updated separately.
14. **Public fixtures.** Tests and examples in this repo use only public material.

## Milestones

Biotope:

- **B1 Extraction** (done, PR #55). The extraction stage, the extractor contract and the LLM extractor, tested on InTRAC's six papers, REACH's CHC pages and ERC calls.
- **B2 Releases and input checks.** The build checks its input files against their descriptions' sha256 and refuses a mismatch, the run record holds no record values so a project can commit it, and biotope diffs two builds by object ID. Nothing else.
- **B3 What REACH pass 1 shows biotope lacks.** Unspecified until pass 1 reports its gaps; each gap is mapped against what exists before its spec.
- **B4 Evolving projects.** A topology change carries IDs and decisions across, and biotope reports what changed in sources, extraction and contracts, and what needs review. Its spec follows the rule for new milestones: contract drift, B1's run report and B2's diff already cover part of this.

REACH, in its own repo:

- **Pass 1.** REACH built as a new biotope project from raw data, to test the new-project flow, with its registry, Anna's corrections and its source priorities as project code in alignment and mappings. It needs nothing from B2 and can start now, in parallel with B2. It does not replace REACH's pipeline.
- **Pass 2.** The pass-1 project evolves: ERC calls arrive as a new entity, and IDs and Anna's decisions carry across. Pass 2 is what lands, first on REACH's test base only. REACH's apps (Airtable, search, MCP) stay in REACH and read the release.

Until pass 2 lands, fixes from Anna's feedback go into REACH's current pipeline, and each fix joins what pass 2 must reproduce.
