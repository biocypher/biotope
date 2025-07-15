# Biotope Init

!!! warning "Draft stage"

    Biotope is in draft stage. Functionality may be missing or incomplete.
    The API is subject to change.

## Overview

The `biotope init` command initializes a new biotope project with interactive configuration. It sets up the necessary directory structure and configuration files for metadata management.

## Features

### Interactive Configuration

The init process guides you through several configuration options:

1. **Project Name**: Set a name for your biotope project
2. **Git Integration**: Choose whether to initialize Git version control
3. **Knowledge Graph**: Optionally install a knowledge graph for enhanced data management
4. **Output Format**: Select output format (only shown if knowledge graph is enabled)
5. **Project Metadata**: Collect project-level metadata for annotation pre-filling

### Project-Level Metadata Collection

During initialization, you can optionally collect project-level metadata that will be used to pre-fill annotation fields:

- **Description**: Brief description of the project and its purpose
- **URL**: Project homepage, repository, or documentation URL
- **Creator**: Name and contact information of the project maintainer
- **License**: Data usage license (e.g., MIT, CC-BY, etc.)
- **Citation**: How to cite the project or dataset

This metadata is stored in `.biotope/config/biotope.yaml` and automatically loaded when using `biotope annotate interactive`.

### Conditional Output Format Selection

The output format selection is only presented if you choose to install a knowledge graph, as it's only relevant for knowledge graph functionality.

## Usage

```bash
biotope init [OPTIONS]
```

### Options

- `--dir, -d`: Directory to initialize biotope project in (default: current directory)

### Example

```bash
# Initialize in current directory
biotope init

# Initialize in specific directory
biotope init --dir /path/to/project
```

## Configuration File Structure

The initialization creates a `.biotope/config/biotope.yaml` file with the following structure:

```yaml
version: "1.0"
croissant_schema_version: "1.0"
default_metadata_template: "scientific"
data_storage:
  type: "local"
  path: "data"
checksum_algorithm: "sha256"
auto_stage: true
commit_message_template: "Update metadata: {description}"

# Project information (consolidated from internal metadata)
project_info:
  name: "my-project"
  created_at: "2024-01-01T00:00:00Z"
  biotope_version: "0.1.0"
  last_modified: "2024-01-01T00:00:00Z"
  builds: []
  knowledge_sources: []

# Project-level metadata for annotation pre-fill
project_metadata:
  description: "Project description"
  url: "https://example.com/project"
  creator:
    name: "John Doe"
    email: "john@example.com"
  license: "MIT"
  citation: "Doe, J. (2024). Project Title. Journal Name."

# Validation configuration
annotation_validation:
  enabled: true
  minimum_required_fields:
    - "name"
    - "description"
    - "creator"
    - "dateCreated"
    - "distribution"
  field_validation:
    name:
      type: "string"
      min_length: 1
    description:
      type: "string"
      min_length: 10
    creator:
      type: "object"
      required_keys: ["name"]
    dateCreated:
      type: "string"
      format: "date"
    distribution:
      type: "array"
      min_length: 1
```

## Directory Structure

The init command creates the following directory structure:

```
project-root/
├── .biotope/
│   ├── config/
│   │   └── biotope.yaml          # Consolidated configuration (Git-like)
│   ├── datasets/                 # Croissant ML metadata files
│   ├── workflows/                # Bioinformatics workflow definitions
│   └── logs/                     # Command execution logs
├── config/
│   └── biotope.yaml              # User-facing configuration
├── data/
│   ├── raw/
│   └── processed/
├── schemas/
└── outputs/
```

**Note**: The configuration follows a Git-like approach where `.biotope/config/biotope.yaml` contains all biotope-specific configuration, similar to how Git uses `.git/config` for its configuration.

## Managing Project Metadata

After initialization, you can manage project metadata using the `biotope config` command:

```bash
# Set project metadata
biotope config set-project-metadata

# Show current project metadata
biotope config show-project-metadata
```

::: biotope.commands.init
