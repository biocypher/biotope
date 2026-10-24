# Roadmap: data products

Biotope 0.10 builds a typed knowledge graph from local structured files in one pure pass. The next version makes biotope a reusable framework for building and maintaining a **data product**: a versioned representation of a domain, built from local sources of any kind, structured or not, and kept current as data and needs change.

REACH, the Computational Health Center's register of who works on what ([slolab/reach](https://github.com/slolab/reach)), is the testing ground. It needs what 0.10 lacks: web pages as sources, IDs that people's edits point at, human corrections that survive every rebuild, and a topology that grows. InTRAC, with its published papers, is the second user, and the ELIXIR Atlas is expected to be the third. A feature belongs in biotope only if it makes sense beyond REACH.

This roadmap records the premises and decisions from the alignment of 22 October 2026. Each milestone gets a spec in `docs/specs/` and one PR.

## Terms

- **Data product:** the versioned output of a biotope project, a release of typed records with provenance. The BioCypher graph and SQLite are exports of a release.
- **Unstructured source:** a local document whose content has no record structure, such as an HTML page, a PDF or a grant call. Croissant-baker describes it as a bare file.
- **Extraction:** the stage that turns unstructured sources into structured records under a reviewed extraction schema. Its output is an ordinary structured source.
- **Extraction schema:** the fields extraction fills for one kind of document. It is not the topology: the mapping from extracted records to topology objects is ordinary mapping.
- **Extractor:** a swappable implementation of extraction. The first calls an LLM; a later one applies rules an agent writes.
- **Release:** one immutable build of a project, with its manifest, provenance and the problems and conflicts it found.
- **Committed state:** files a project commits and every build reads and extends: the ID registry and the release history. Human decisions are an input dataset, which a project may commit.
- **Human decision:** a person's judgement on a record, such as accepting or rejecting a match, overriding a field or excluding a link. It is an input to the build.

## Lifecycle

```text
local documents ── extraction ── extracted records ─┐
                                                    ├─ croissant-baker ── reviewed sources
local structured files ─────────────────────────────┘                          │
                                                                               ▼
IDs, release history, decisions ────────────► alignment, precedence, mappings ──► release
                                                                               │
                                                             graph, SQLite, project apps
```

A **new project** starts from raw data and its purpose. An agent proposes the extraction schemas, the topology and the mappings, and a person reviews them.

An **evolving project** meets two kinds of change. New rows in a known source need only a mechanical rebuild. A new kind of source, or a new need, may change the topology; that change is reviewed, and the rebuild carries existing IDs and human decisions across it. Biotope tells the user or agent what changed and what must be reviewed.

## Decisions

1. **Biotope's scope.** Biotope owns the representation of the data and its mapping: extraction, sources, identity, precedence, topology, committed state and releases. It is never a fetcher or scraper, a scheduler, an application layer (search, user interfaces, writing back to tools such as Airtable), a general ETL tool, or a judge of equivalence. Downloading a source is a script the project adds.

1. **Extraction is a stage before `add`.** A raw document goes through an extractor into a stored, derived dataset (`prov:wasDerivedFrom`, status `processed`). Croissant-baker then describes it like any other file. `graph build` stays deterministic and offline.

1. **The extractor contract.** An extractor takes documents and a reviewed extraction schema, and returns records that match the schema. Each record points to its document and each field carries its evidence, the quoted span or a locator. An extractor declares its name and version. Whether it uses an agent or generated rules is hidden behind the contract.

1. **Extraction is stored and reproducible.** Extracted records are versioned with their provenance: document hash, schema revision, extractor name and version, model and endpoint. A document is extracted again only when one of these changes.

1. **The LLM extractor calls an OpenAI-compatible API.** OpenRouter and the HMGU endpoint both serve one. The endpoint URL is project configuration and may be written literally, since it is not a secret. The key always comes from an environment variable that the configuration names. The model is chosen after research, not by default.

1. **Public inputs only in this version.** Only public documents go to an external model: public HTML pages, public ERC calls and InTRAC's published papers. Internal sources, such as presentations and contracts, come later and will need a per-source policy.

1. **People review artefacts, not records.** An agent proposes the extraction schemas, the topology and the mapping priorities and conflict resolution from the project's purpose, and a person reviews them. The rest follows the `biotope-croissant` skill: the user owns scientific decisions, the agent engineering ones, and the agent stops and asks before merging identities without a shared accession.

1. **Builds are pure.** A build is a function of its inputs and the project's committed files. The ID registry and the release history are committed files that biotope defines generically and every build reads and extends. Human decisions are an input dataset whose shape biotope defines, and each project chooses whether to commit it: REACH reads Anna's from Airtable at each build, so names and emails stay out of git (Vlad, 23 October 2026: "ok" to "decisions such as Anna's corrections are an input dataset"). Biotope keeps no hidden state.

1. **Identity and precedence are explicit.** Today the build refuses conflicting values and leaves resolution to Python in the mappings, and `alignment/` is an empty template. The new version makes both explicit, reviewable artefacts. Matching rules stay project code.

1. **Stable IDs where outside things point.** Entities with natural keys, such as genes, cell types and DOIs, keep them. Entities without one that something outside the build refers to get a registered ID that never changes and is never reused, with aliases and the date each was first seen. For kinds a project registers, natural keys are aliases of the persistent ID.

1. **Human decisions survive change.** A decision is a record about a thing that keeps changing. Biotope applies these rules for every project:

   - a rejected match stays rejected when the sources propose it again;
   - a decision follows its target when that target's ID is merged into another;
   - an override retires when the source starts to agree with it;
   - a source change under an override is flagged for review, and the override stays;
   - two conflicting decisions are flagged, never ranked;
   - an invalid decision drops only itself and is reported with its reason.

   Interfaces for making decisions, such as REACH's Airtable tables and field sync, stay in the project.

1. **Releases have history.** Every build produces a release with a manifest and a diff against the previous one. A release records its exact inputs through what Croissant already holds, each file's sha256 and size, and the build refuses or flags an input file that no longer matches its manifest. A past release can be rebuilt from its inputs and the committed state at that point while the project keeps those input files; biotope stores no raw snapshots (Vlad, 23 October 2026: "wouldn't it be too much? And doesn't croissant already do that? Let's not overbuild this part, reuse existing tools if possible").

1. **Breaking 0.10 is allowed.** Biotope is before 1.0. Each break gets a note in `migration.md`. biotope-bench is updated separately.

1. **Public fixtures.** Tests and examples in this repo use only public material.

## Milestones

Biotope:

- **B1 Extraction.** The extraction stage, the extractor contract and the LLM extractor. Schemas are proposed from the purpose and reviewed. Tested on InTRAC's six papers, REACH's CHC pages and two or three ERC calls.
- **B2 Identity and precedence.** Explicit, reviewable identity (declared keys and aliases, merges on shared keys, contradictions flagged) and field precedence with listed conflicts. B2 stores nothing.
- **B3 Committed state.** The ID registry, human decisions (match decisions, overrides and link edits) under decision 11, and release history with diffs and input checks under decision 12.
- **B4 Evolving projects.** A topology change carries IDs and decisions across. Biotope reports what changed in sources, extraction and contracts, and what needs review.

REACH, in its own repo:

- **Pass 1.** REACH built as a new biotope project from raw data, to test the new-project flow. It does not replace REACH's pipeline.
- **Pass 2.** The pass-1 project evolves: ERC calls arrive as a new entity, and IDs and Anna's decisions carry across. Pass 2 is what lands, first on REACH's test base only. REACH's apps (Airtable, search, MCP) stay in REACH and read the release.

Until pass 2 lands, fixes from Anna's feedback go into REACH's current pipeline, and each fix joins what pass 2 must reproduce.
