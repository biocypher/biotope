
The `biotope annotate` module provides tools for creating and managing metadata annotations using the Croissant ML schema. This document provides detailed examples and instructions for working with different layers of Croissant ML.

## Installation

```bash
pip install biotope
```

## Basic Usage

The annotation module can be used in several ways:

```bash
# Interactive mode with project metadata pre-fill
biotope annotate interactive

# Interactive mode for staged files
biotope annotate interactive --staged

# Interactive mode for incomplete tracked files
biotope annotate interactive --incomplete

# Create metadata from CLI parameters
biotope annotate create

# Validate existing metadata
biotope annotate validate --jsonld <file_name.json>

# Load existing record
biotope annotate load
```

## Project Metadata Pre-fill

Biotope supports automatic pre-filling of annotation fields using project-level metadata. This feature makes the annotation process faster and ensures consistency across all datasets in your project.

### Setting Up Project Metadata

Project metadata can be set during initialization or later using the config command:

```bash
# During initialization
biotope init

# Or set project metadata later
biotope config set-project-metadata
```

### Pre-fill Fields

The following fields are automatically pre-filled from project metadata:

- **Description**: Project description (if not already specified)
- **URL**: Project homepage or repository URL
- **Creator**: Project creator name and email
- **License**: Project license
- **Citation**: Project citation information

### Pre-fill Priority

When pre-filling metadata, the following priority order is used:

1. **Command-line prefill**: Metadata provided via `--prefill-metadata`
2. **Project metadata**: Metadata from `.biotope/config/biotope.yaml`
3. **Default values**: Built-in defaults for required fields

### Example Workflow

```bash
# 1. Set up project metadata
biotope config set-project-metadata
# Enter: Project description, URL, creator, license, citation

# 2. Add files to your project
biotope add data/raw/experiment.csv

# 3. Annotate with pre-filled metadata
biotope annotate interactive --staged
# Form will be pre-filled with project metadata
```

## Croissant ML Layers

Croissant ML organizes metadata in several layers, each serving a specific purpose in describing your dataset.

### 1. Dataset Layer

The dataset layer provides high-level information about your entire dataset.

Example:
```json
{
  "@type": "sc:Dataset",
  "name": "Example Dataset",
  "description": "A sample dataset for demonstration",
  "license": "MIT",
  "version": "1.0.0",
  "datePublished": "2024-03-20",
  "creator": {
    "@type": "Person",
    "name": "John Doe"
  }
}
```

### 2. Distribution Layer

The distribution layer describes how the dataset is distributed and accessed.

Example:
```json
{
  "@type": "sc:DataDownload",
  "name": "Dataset Distribution",
  "contentUrl": "https://example.com/dataset.zip",
  "encodingFormat": "application/zip",
  "contentSize": "1.2GB",
  "sha256": "abc123..."
}
```

### 3. Record Set Layer

The record set layer defines the structure of your data records.

Example:
```json
{
  "@type": "sc:RecordSet",
  "name": "Main Records",
  "description": "Primary data records",
  "field": [
    {
      "@type": "sc:Field",
      "name": "id",
      "description": "Unique identifier",
      "dataType": "string"
    },
    {
      "@type": "sc:Field",
      "name": "value",
      "description": "Numerical value",
      "dataType": "float"
    }
  ]
}
```

### 4. Field Layer

The field layer provides detailed information about individual data fields.

Example:
```json
{
  "@type": "sc:Field",
  "name": "temperature",
  "description": "Temperature measurement in Celsius",
  "dataType": "float",
  "unit": "celsius",
  "minimum": -273.15,
  "maximum": 100.0
}
```

## Best Practices

1. **Set Project Metadata Early**: Configure project-level metadata during initialization or early in the project lifecycle
2. **Completeness**: Always provide as much metadata as possible for each layer
3. **Consistency**: Use consistent naming conventions and data types
4. **Validation**: Regularly validate your metadata using `biotope annotate validate`
5. **Versioning**: Include version information for both the dataset and metadata
6. **Team Coordination**: Ensure all team members use the same project metadata for consistency

## Common Use Cases

### Creating a New Dataset Annotation

1. Start with the interactive mode:
```bash
biotope annotate interactive
```

2. Follow the prompts to enter:
   - Dataset information (name, description, license) - pre-filled from project metadata
   - Distribution details (format, size, URL)
   - Record structure (fields, data types)
   - Field-specific metadata (units, ranges, descriptions)

### Annotating Staged Files

If you have files staged with `biotope add`, you can annotate them all at once:

```bash
# Add files to staging
biotope add data/*.csv

# Annotate all staged files interactively with project metadata pre-fill
biotope annotate interactive --staged
```

This will run the interactive annotation process for each staged file, pre-filling metadata with both file information and project metadata.

### Completing Incomplete Annotations

If you have tracked files with incomplete metadata (missing required fields), you can complete them:

```bash
# Check which files need annotation
biotope status

# Complete annotations for all incomplete tracked files
biotope annotate interactive --incomplete
```

This will find all tracked files that don't meet the minimum annotation requirements and allow you to complete their metadata interactively with project metadata pre-fill.

### Custom Pre-fill Metadata

You can override project metadata with custom values:

```bash
# Pre-fill with custom metadata
biotope annotate interactive --prefill-metadata '{"description": "Custom description", "license": "CC-BY"}'
```

### Validating Existing Annotations

```bash
biotope annotate validate --jsonld my_dataset.json
```

This will check your metadata against the Croissant ML schema and report any issues.

## Managing Project Metadata

### View Current Project Metadata

```bash
biotope config show-project-metadata
```

### Update Project Metadata

```bash
biotope config set-project-metadata
```

### Example Project Metadata Configuration

```yaml
project_metadata:
  description: "A comprehensive dataset for protein structure analysis"
  url: "https://github.com/example/protein-data"
  creator:
    name: "Dr. Jane Smith"
    email: "jane.smith@university.edu"
  license: "MIT"
  citation: "Smith, J. et al. (2024). Protein Structure Dataset. Nature Data."
```

## Future Improvements

The following features are planned for future releases:
- Automatic metadata extraction from file contents
- Integration with LLMs for automated annotation
- File download and automatic annotation
- Enhanced validation capabilities
- Support for additional Croissant ML fields
- Advanced project metadata templates

## Related Resources

- [Croissant ML Documentation](https://research.google/blog/croissant-a-metadata-format-for-ml-ready-datasets/)
- [BioCypher Documentation](https://biocypher.org)
- [Unit Tests](https://github.com/biocypher/biotope/blob/main/tests/commands/test_annotate.py) 
