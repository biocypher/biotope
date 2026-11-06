# Biotope

Biotope is a framework that helps your AI agents build and maintain purpose-driven knowledge representations.
Imagine you need to build a knowledge graph that uses messy clinical data to find promising drug targets, or maintain a database of all people, events, and resources of a distributed organization. You can give raw data and **the purpose statement** to the biotope agent and it will build the graph topology, mapping, entity and conflict resolution, following the industry best practices. Biotope simplifies the process of building and maintaining the data project, but semantic authority and final decisions on the representation stays with the human.

How data projects that are created by the biotope agent work:

- **Inputs.** Structured files are described automatically using croissant-baker: CSV, TSV, Excel, Parquet, JSON, HDF5 and AnnData, FHIR, VCF, BAM, FASTA, DICOM, NIfTI, images and more. Unstructured documents, such as papers and web pages, become records through an extractor the agent writes, and each value keeps the quote it came from.
- **Output.** Neo4j import files or one SQLite file. Every node and edge names the source rows it came from.
- **Maintainability.** The biotope-created data project is plain Python in a fixed layout and static type-checking for all entities and mappings. New data of the same shape rebuilds with commands only, and a change in the data's structure is reported before the build.
- **Versioning.** Everything Biotope writes is a plain file that you commit with your own git. Each build records its code, data revisions and library versions.

## Start here

- [Get started](get-started.md): install the plugin and start a project.
- [Working with the agent](agent.md): the purpose statement, your decisions and the review.
- [Use the result](result.md): load the graph into Neo4j, query it in SQLite and trace its values.

## Limits

- Biotope does not decide which records are the same thing. You or the agent decide, and the agent records the decision.
- The checks test the structure of the graph. Review its content against the sources.
- The whole graph is held in memory during a build, so choose a scope that fits the machine.

## Versions

Biotope follows [semantic versioning](https://semver.org/): a change that breaks your project comes in a new major version. The [changelog](https://github.com/biocypher/biotope/blob/main/CHANGELOG.md) lists the changes in each release.
