# Decisions

Each decision gives its date and reason. A new decision is added here when it is made, and plans and status stay in issue [#53](https://github.com/biocypher/biotope/issues/53).

## What Biotope does and what stays in the project

Biotope is a framework for data representation. It describes sources, extracts records from documents, and checks, runs and exports the topology, alignment and mappings that each project writes as its own code.

Everything specific to one project stays in that project, such as downloading data or writing to a tool like Airtable. Biotope is not a fetcher, a scraper, a scheduler, an application layer or a general ETL tool. It never decides by itself which records are the same thing. The project owns identities, units, null handling, join cardinality and exclusions; Biotope supplies the contracts that record and check those decisions.

Three parts already exist for this: shared terms in the project's `graph/standardization.py`, the alignment stage in the project's `graph/alignment/`, and the conflict guard, which stops a build when two graph objects with one ID have different values.

**Why:** Biotope grows from real projects, not from a design made up front: first REACH, the register of who works on what at Helmholtz Munich's Computational Health Center, and InTRAC, a biomedical graph. The long-term goal is a project that an AI agent maintains without an engineer, and each decision is weighed against it.

## Biotope adds only what a real project shows is missing

October 2026, #53. **Why:** a feature without a project that needs it has no test of whether it is right.

## Git belongs to the project

26 October 2026. Biotope does not require git and never writes to it: no `git init`, staging or commits. When a repository exists, Biotope reads its ignore rules to warn that a file it wrote must be committed. **Why:** the project decides how it versions its files, and a tool that commits for it takes that decision away.

## IDs come from paths

26 October 2026. A file's ID is its path within its dataset, and a table's ID is its file's ID and its name in the file. **Why:** new data of the same shape then keeps every ID, so a project rebuilds with commands only, and no code or annotation changes.

## The annotation file is the one place people write about a dataset

26 October 2026. The manifest is the data as croissant-baker describes it, with the annotation file applied over it. Nobody edits the manifest. **Why:** a rebake then always succeeds and keeps every annotation, and people and agents have one place to write.

## Projects write their own extractors

4 November 2026. A project writes one extractor per kind of document in its graph workspace. Biotope runs it, validates and stores the records with their evidence, and registers them as an ordinary dataset. Biotope ships no extractor. **Why:** reading a document well depends on how it is built, and that is project knowledge. The runner's reuse, evidence and registration are the same for every project.

## Stable node IDs are read back from where they are stored

5 November 2026. Every build is a full rebuild. A project whose IDs nothing outside the build stores builds them from source keys. A project whose IDs live in another system, as REACH's live in Airtable, reads them back from that system's export as a source, and only new things get new IDs. A committed key map is kept only when IDs cannot be read back. Human corrections are an input dataset that every build applies. **Why:** a full rebuild is simple and reproducible, and the IDs stay stable without state hidden in the build.

## Each project runs Biotope in its own environment

5 November 2026. `graph/pyproject.toml` declares Biotope and the libraries the graph code reads data with, `graph/uv.lock` pins them, and commands run as `uv run --project graph biotope …`. **Why:** Biotope imports the graph code and type-checks it against those libraries, so it belongs in the project's environment, as uv advises for tools such as pytest. The lockfile makes builds reproducible, and projects stay apart.

## Release 1.0 keeps no backward compatibility

5 November 2026. Release 1.0 reads only what 1.0 writes. Every project rebuilds with the new version, and the docs describe only current behavior. **Why:** no project outside the maintainer's depends on earlier versions, and code and text about past behavior cost every reader time. From 1.0 on, the versioning promise in [conventions.md](conventions.md#versioning) applies.
