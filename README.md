# Biotope

[![PyPI](https://img.shields.io/pypi/v/biotope.svg)](https://pypi.org/project/biotope/)
[![Python](https://img.shields.io/pypi/pyversions/biotope.svg)](https://pypi.org/project/biotope/)
[![Documentation](https://github.com/biocypher/biotope/actions/workflows/docs_mkdocs.yaml/badge.svg)](https://biocypher.github.io/biotope/latest/)
[![License](https://img.shields.io/pypi/l/biotope.svg)](https://github.com/biocypher/biotope/blob/main/LICENSE)

Biotope is a framework that helps your AI agents build and maintain purpose-driven knowledge representations.
Imagine you need to build a knowledge graph that uses messy clinical data to find promising drug targets, or maintain a database of all people, events, and resources of a distributed organization. You can give raw data and **the purpose statement** to the biotope agent and it will build the graph topology, mapping, entity and conflict resolution, following the industry best practices. Biotope simplifies the process of building and maintaining the data project, but semantic authority and final decisions on the representation stays with the human.

How data projects that are created by the biotope agent work:

- **Inputs.** Structured files are described automatically using croissant-baker: CSV, TSV, Excel, Parquet, JSON, HDF5 and AnnData, FHIR, VCF, BAM, FASTA, DICOM, NIfTI, images and more. Unstructured documents, such as papers and web pages, become records through an extractor the agent writes, and each value keeps the quote it came from.
- **Output.** Neo4j import files or one SQLite file. Every node and edge names the source rows it came from.
- **Maintainability.** The biotope-created data project is plain Python in a fixed layout and static type-checking for all entities and mappings. New data of the same shape rebuilds with commands only, and a change in the data's structure is reported before the build.
- **Versioning.** Everything Biotope writes is a plain file that you commit with your own git. Each build records its code, data revisions and library versions.

## Get started

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and an agentic harness (e.g Claude Code, Codex, open-code, etc.).

1. In your agentic harness, add the Biotope marketplace and install the plugin:

    <!-- x-release-please-start-version -->
    ```text
    /plugin marketplace add biocypher/biotope#biotope-v1.0.0
    /plugin install biotope@biotope
    ```
    <!-- x-release-please-end -->

2. Start your agent in your project folder.
3. Tell it where the data is and what the graph is for:

    > Use biotope to build a knowledge graph from the files in `data/`. It is for our institute's staff, who look up who works on which topic, in which group and on which projects.

The agent installs Biotope into the project's own environment, agrees the purpose with you and asks for the decisions only you can make. [Get started](https://biocypher.github.io/biotope/latest/get-started/) walks through each step, including Cursor and Codex.

## Documentation

- [Working with the agent](https://biocypher.github.io/biotope/latest/agent/): the purpose statement, your decisions and the review.
- [Use the result](https://biocypher.github.io/biotope/latest/result/): load the graph into Neo4j or query it in SQLite.
- [Your project](https://biocypher.github.io/biotope/latest/project/): what to commit and how to rebuild after new data.
- [CLI reference](https://biocypher.github.io/biotope/latest/cli/).

## Contribute

See [CONTRIBUTING.md](https://github.com/biocypher/biotope/blob/main/CONTRIBUTING.md). Report problems through [GitHub issues](https://github.com/biocypher/biotope/issues).

Typed authoring and modular topology construction were informed by Paul Ka Po To's `kg-build-system`. Biotope does not depend on that engine.

Copyright © 2025–2026 BioCypher Team. [Apache 2.0](https://github.com/biocypher/biotope/blob/main/LICENSE).
