# Biotope

*CLI integration for BioCypher ecosystem packages*

!!! info "Biotope is still under development"

    Biotope is still under development and the API is subject to change.
    The package is currently only meant for developer use and prototyping.

The *Biotope* CLI integration is our attempt to integrate our open source ecosystem
packages into an accessible suite for scientific knowledge management. We are
first approaching the project from a CLI perspective, as this is the most basic
technology for prototyping automated workflows. We aim to extend this towards
other user-interfaces, such as web apps, in the future.

*Biotope* contains various modules for different tasks, some of which are
straightfoward applications of existing ecosystem packages, while others
are prototypes for new features. See more information in the API documentation.

- `biotope init`: Initialize a new project
- `biotope status/add/commit/log/push/pull`: Manage metadata in a git-like fashion
- `biotope get`: Download files from a URL and stage them for annotation and version control
- `biotope annotate`: Annotate your data with consistent metadata in Croissant ML
- `biotope check-data`: Perform consistency checks for file integrity
- `biotope mv`: Move tracked files and update metadata automatically
- `biotope config`: Manage project configuration and metadata settings
- `biotope build`: Build a [BioCypher](https://biocypher.org) knowledge representation
- `biotope chat`: Chat with a project using [BioChatter](https://biochatter.org)
- `biotope agent`: Plan agentic workflows using [BioChatter](https://biochatter.org)
- `biotope read`: Extract information from unstructured modalities (BioGather)
- `biotope view`: Use visual analysis tools to interpret your data and metadata

## Git Integration for Metadata Version Control

Biotope uses a **Git-on-Top** strategy for metadata version control, providing:

- **Version control** for all metadata changes using Git
- **Collaboration** through standard Git workflows
- **Data integrity** through checksum verification
- **Familiar tooling** - all Git tools work seamlessly

### Core Git-Integrated Commands

- `biotope add`: Stage data files for metadata creation
- `biotope mv`: Move tracked data files and update metadata
- `biotope get`: Download remote files and stage them for metadata creation
- `biotope status`: Show current project status
- `biotope commit`: Commit metadata changes using Git
- `biotope log`: View commit history
- `biotope push/pull`: Share metadata with remote repositories
- `biotope check-data`: Verify data integrity against checksums

### Basic Workflow

```bash
# Initialize project (with Git, .gitignore, and optional project metadata)
biotope init

# Add local data files (creates metadata, ignored by Git by default)
biotope add data/raw/experiment.csv

# Or add new files at once, recursively
biotope add -r data

# Or download and stage remote files (calls `add` once finished)
biotope get https://example.com/data/experiment.csv

# Check status (shows metadata changes, not data files)
biotope status

# Create metadata for staged files (with project metadata pre-fill)
biotope annotate interactive --staged

# Or complete incomplete annotations
biotope annotate interactive --incomplete

# Commit changes (metadata only, data files excluded via .gitignore)
biotope commit -m "Add experiment dataset"

# View history
biotope log --oneline
```

**Note**: Data files are automatically excluded from Git tracking via `.gitignore`. Only metadata is version controlled, keeping repositories small and focused.

### Project-Level Metadata

Biotope supports project-level metadata collection during initialization that can be used to pre-fill annotation fields:

- **Description**: Project description and purpose
- **URL**: Project homepage or repository
- **Creator**: Project maintainer information
- **License**: Data usage license
- **Citation**: How to cite the project

This metadata is stored in `.biotope/config/biotope.yaml` and automatically pre-fills fields when using `biotope annotate interactive`.

### Documentation

- **[Git Integration for Users](git-integration.md)**: Learn how to use biotope's Git integration, leveraging your existing Git knowledge
- **[Git Integration for Developers](git-integration-dev.md)**: Understand the technical implementation and architecture
- **[Cluster Compliance](cluster-compliance.md)**: How to enforce and check metadata validation policies across clusters

## Metadata annotation using Croissant, short guide

The `biotope` package features a metadata annotation assistant using the
recently introduced
[Croissant](https://research.google/blog/croissant-a-metadata-format-for-ml-ready-datasets/)
schema. It is available as the `biotope annotate` module. Usage:

```
pip install biotope
biotope annotate interactive
```

You can also use the `biotope get` command to download files and stage them for annotation and version control:

```
biotope get https://example.com/data/file.txt
biotope status
biotope annotate interactive --staged
biotope commit -m "Add new dataset from URL"
```

This will download the file, stage it for annotation, and fit into the same workflow as local files.

**Project Metadata Pre-fill**: If you've set up project-level metadata during `biotope init`, the annotation form will be pre-filled with this information, making the annotation process faster and more consistent.

After creation, `biotope` can also be used to validate the JSON-LD (CAVE: being
a prototype, biotope does not yet implement all croissant fields):

```
biotope annotate validate –jsonld <file_name.json>
```

`biotope` also has the method `biotope annotate create` to create metadata files
from CLI parameters (no interactive mode) and `biotope annotate load` to load an
existing record (the use of this is not well-defined yet). Further improvements
would be the integration of LLMs for the automation of metadata annotations from
file contents (using the `biochatter` module of `biotope`).

Unit tests to inform about further functions and details can be found at
https://github.com/biocypher/biotope/blob/main/tests/commands/test_annotate.py
and https://github.com/biocypher/biotope/blob/main/tests/commands/test_get.py

## Further Reading

- [Annotation Validation and Status Reporting](git-integration.md#annotation-validation-and-status-reporting): How to ensure your datasets are properly annotated and how to configure requirements (user guide).
- [Developer & Admin Guide: Annotation Validation](git-integration-dev.md#developer--admin-guide-annotation-validation): How to customize, extend, and manage annotation validation (admin/dev guide).
- [Cluster Compliance](cluster-compliance.md): Cluster-wide enforcement, compliance checking, and best practices.

## Copyright

- Copyright © 2025 BioCypher Team.
- Free software distributed under the MIT License.
