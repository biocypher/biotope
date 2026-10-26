# Roadmap

This roadmap is written from issue [#53](https://github.com/biocypher/biotope/issues/53), the source of truth for new work on biotope's next version. When this page, a spec, a PR or a comment disagrees with #53, #53 wins. #53 changes only on the decision of Vlad, the maintainer, and lists each change with its date. It replaces the plan of 22 October 2026 ([#52](https://github.com/biocypher/biotope/pull/52)). Live status is in #53.

## Goal

- Biotope is a framework for data representation. It turns a project's local sources, structured files and documents alike, into a graph of typed records that answers the project's questions, and rebuilds the graph when the data changes.
- It grows from real problems, not from a design made up front. The first is REACH, the register of who works on what at Helmholtz Munich's Computational Health Center. The ELIXIR Atlas follows later. Both run alongside biotope's benchmark work on graph representation and ephemeral graph building.
- Biotope is developed in an agile way and specialized later by what sticks. It must work across projects like REACH and the ELIXIR Atlas, but for now it is built and tested with REACH only, plus the InTRAC build below.
- Long-term goal: a project built on biotope can be maintained by AI, without an engineer. This is not tested now, but every architecture decision weighs it.

## What biotope does and what stays in the project

- Biotope is the framework for the representation and its mapping. It describes sources, extracts documents into records, and checks, runs and exports the project's topology, alignment and mappings, which the project writes as its own code.
- Everything specific to a project stays in that project, such as downloading data or writing to tools like Airtable. Biotope is never a fetcher or scraper, a scheduler, an application layer or a general ETL tool, and it never decides on its own which records are the same thing.
- 0.10's principle holds: "The project owns identities, units, null handling, join cardinality and exclusions. Biotope supplies contracts for recording and checking those decisions" ([architecture](architecture.md)).
- Three parts of this already exist:
  - harmonization, in the project's `graph/standardization.py`, which `biotope graph check` reports on;
  - the alignment stage, in the project's own `graph/alignment/` folder. `biotope graph scaffold` creates it from the template `biotope/templates/graph/alignment/__init__.py`; it is project code, not a biotope module;
  - the conflict guard: a build stops when two graph objects with one ID have different values, and the project resolves the conflict in its pipeline.
- Biotope adds only what a real project shows is missing.

## Decisions

1. **Extraction** (done, [#55](https://github.com/biocypher/biotope/pull/55)). An unstructured document goes through a swappable extractor into stored, structured records with evidence, which are then an ordinary source. The LLM extractor is first; a rule-based one comes later behind the same contract. See [Extraction](extraction.md).
1. **Stable IDs follow common industry practice.** Every build is a full rebuild. A project whose IDs nothing outside the build stores, such as InTRAC with its Ensembl gene IDs, needs nothing more. A project whose IDs are stored outside the build, as REACH's are in its Airtable rows, also keeps one committed key map: every alias (DOI, PMID, email, ORCID and so on) points to a permanent ID, an ID merged into another redirects to it, and no ID is ever reused. Human corrections are an input dataset that every build applies. The key map stays project code until a second project needs the same thing; then it moves into biotope.
1. **Public documents only** go to external models in this version: public web pages, public ERC calls and InTRAC's published papers.
1. **Testing and development** use only `deepseek/deepseek-v4.1-flash` through OpenRouter. The bar is reasonable results and an end-to-end run, not full accuracy.

## This sprint

Done by the end of the week of 26 October 2026. The ELIXIR Atlas hackathon follows soon after.

1. **REACH from scratch.** A new biotope project builds REACH's data from REACH's raw data and its existing ID registry. The CHC website pages go through extraction. For every output file, IDs and values match the current REACH pipeline's output from the same raw data, except for differences that are listed and approved by Vlad. REACH's own tools (Airtable push, search index, Claude plugin) work on it.
1. **REACH iteration**, two cases:
   - New data arrives: after a fresh download, the build runs again with no code or configuration change. Every existing ID names the same thing, every human correction still applies, and new things get new IDs.
   - A new table: two or three public ERC calls are extracted into a new entity. Existing IDs and corrections carry over, and biotope shows what changed and what needs review.
1. **InTRAC.** Its graph builds on biotope's main branch, including extraction from its published papers.

## Out of scope

Testing AI maintenance, the ELIXIR Atlas, internal documents, and switching REACH's production data.

## How the work runs

- REACH's biotope project is built first, in REACH's own repository on its test data. Whatever biotope cannot do becomes an issue and a small PR here; whatever is REACH-specific stays in REACH.
- Each spec opens with a map of what biotope already does for its need, verified in code, and covers only the gap. The format is in [`specs/README.md`](specs/README.md).
