# Biotope Annotate

!!! warning "Draft stage"

    Biotope is in draft stage. Functionality may be missing or incomplete.
    The API is subject to change.

## Overview

The `biotope annotate` command creates dataset metadata definitions in Croissant format. It provides interactive and programmatic ways to annotate your data with consistent metadata.

## Features

### Interactive Annotation

The `biotope annotate interactive` command provides a user-friendly interface for creating metadata:

- **Project Metadata Pre-fill**: Automatically pre-fills fields with project-level metadata if available
- **Staged Files**: Annotate files that have been staged with `biotope add` or `biotope get`
- **Incomplete Annotations**: Complete or update existing metadata files
- **Validation**: Built-in validation of metadata structure and content

### Project Metadata Integration

When using interactive annotation, biotope automatically loads project-level metadata from `.biotope/config/biotope.yaml` and pre-fills the annotation form with:

- **Description**: Project description (if not already specified)
- **URL**: Project URL
- **Creator**: Project creator information
- **License**: Project license
- **Citation**: Project citation information

This makes the annotation process faster and ensures consistency across all datasets in the project.

## Commands

### `biotope annotate interactive`

Interactive annotation process for files with project metadata pre-fill.

**Usage:**
```bash
biotope annotate interactive [OPTIONS]
```

**Options:**
- `--file, -f`: Specific file to annotate
- `--prefill-metadata`: JSON string with metadata to pre-fill
- `--staged`: Annotate all staged files
- `--incomplete`: Complete incomplete annotations

**Examples:**
```bash
# Interactive annotation with project metadata pre-fill
biotope annotate interactive

# Annotate a specific file
biotope annotate interactive --file data/raw/experiment.csv

# Annotate all staged files
biotope annotate interactive --staged

# Complete incomplete annotations
biotope annotate interactive --incomplete

# Pre-fill with custom metadata
biotope annotate interactive --prefill-metadata '{"description": "Custom description"}'
```

### `biotope annotate create`

Create metadata from command line parameters (non-interactive mode).

**Usage:**
```bash
biotope annotate create [OPTIONS]
```

**Required Options:**
- `--name, -n`: Name of the dataset
- `--data-source, -s`: URL or path to the data source
- `--access-restrictions, -a`: Note on access restrictions (e.g., public, restricted, private)

**Optional Options:**
- `--output, -o`: Output file path (default: metadata.json)
- `--description, -d`: Description of the dataset
- `--contact, -c`: Responsible contact person (default: current user)
- `--date`: Date of creation in ISO format (default: today)
- `--format, -f`: Description of file format
- `--legal-obligations, -l`: Note on legal obligations
- `--collaboration-partner, -p`: Collaboration partner and institute

**Examples:**
```bash
# Create metadata with required fields only
biotope annotate create \
  --name "RNA-seq Dataset" \
  --data-source "https://example.com/rna-seq-data" \
  --access-restrictions "Public"

# Create metadata with all fields
biotope annotate create \
  --name "Proteomics Dataset" \
  --description "Mass spectrometry data from protein samples" \
  --data-source "https://example.com/proteomics-data" \
  --contact "researcher@university.edu" \
  --date "2024-01-15" \
  --access-restrictions "Restricted to academic use" \
  --format "mzML" \
  --legal-obligations "Data sharing agreement required" \
  --collaboration-partner "Proteomics Center, University Hospital" \
  --output "proteomics_metadata.json"
```

**Generated Metadata Structure:**
```json
{
  "@context": {
    "@vocab": "https://schema.org/",
    "cr": "https://mlcommons.org/croissant/",
    "ml": "http://ml-schema.org/",
    "sc": "https://schema.org/",
    "dct": "http://purl.org/dc/terms/",
    "data": "https://mlcommons.org/croissant/data/",
    "rai": "https://mlcommons.org/croissant/rai/",
    "format": "https://mlcommons.org/croissant/format/",
    "citeAs": "https://mlcommons.org/croissant/citeAs/",
    "conformsTo": "https://mlcommons.org/croissant/conformsTo/",
    "@language": "en",
    "repeated": "https://mlcommons.org/croissant/repeated/",
    "field": "https://mlcommons.org/croissant/field/",
    "examples": "https://mlcommons.org/croissant/examples/",
    "recordSet": "https://mlcommons.org/croissant/recordSet/",
    "fileObject": "https://mlcommons.org/croissant/fileObject/",
    "fileSet": "https://mlcommons.org/croissant/fileSet/",
    "source": "https://mlcommons.org/croissant/source/",
    "references": "https://mlcommons.org/croissant/references/",
    "key": "https://mlcommons.org/croissant/key/",
    "parentField": "https://mlcommons.org/croissant/parentField/",
    "isLiveDataset": "https://mlcommons.org/croissant/isLiveDataset/",
    "separator": "https://mlcommons.org/croissant/separator/",
    "extract": "https://mlcommons.org/croissant/extract/",
    "subField": "https://mlcommons.org/croissant/subField/",
    "regex": "https://mlcommons.org/croissant/regex/",
    "column": "https://mlcommons.org/croissant/column/",
    "path": "https://mlcommons.org/croissant/path/",
    "fileProperty": "https://mlcommons.org/croissant/fileProperty/",
    "md5": "https://mlcommons.org/croissant/md5/",
    "jsonPath": "https://mlcommons.org/croissant/jsonPath/",
    "transform": "https://mlcommons.org/croissant/transform/",
    "replace": "https://mlcommons.org/croissant/replace/",
    "dataType": "https://mlcommons.org/croissant/dataType/"
  },
  "@type": "Dataset",
  "name": "Proteomics Dataset",
  "description": "Mass spectrometry data from protein samples",
  "url": "https://example.com/proteomics-data",
  "creator": {
    "@type": "Person",
    "name": "researcher@university.edu"
  },
  "dateCreated": "2024-01-15",
  "datePublished": "2024-01-15",
  "version": "1.0",
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "citation": "Please cite this dataset as: Proteomics Dataset (2024)",
  "cr:accessRestrictions": "Restricted to academic use",
  "encodingFormat": "mzML",
  "cr:legalObligations": "Data sharing agreement required",
  "cr:collaborationPartner": "Proteomics Center, University Hospital",
  "distribution": []
}
```

### `biotope annotate validate`

Validate a Croissant metadata file using the mlcroissant CLI.

**Usage:**
```bash
biotope annotate validate --jsonld <file_name.json>
```

**Options:**
- `--jsonld, -j`: Path to the JSON-LD metadata file to validate (required)

**Examples:**
```bash
# Validate a metadata file
biotope annotate validate --jsonld metadata.json

# Validate with full path
biotope annotate validate --jsonld /path/to/dataset_metadata.json
```

**Output:**
```
Validation successful! The metadata file is valid.
```

**Error Handling:**
- If validation fails, the command will exit with an error code and display validation errors
- Warnings are displayed but don't cause the command to fail
- The command uses the `mlcroissant` CLI under the hood for validation

### `biotope annotate load`

Load records from a dataset using its Croissant metadata.

**Usage:**
```bash
biotope annotate load [OPTIONS]
```

**Required Options:**
- `--jsonld, -j`: Path to the JSON-LD metadata file
- `--record-set, -r`: Name of the record set to load

**Optional Options:**
- `--num-records, -n`: Number of records to load (default: 10)

**Examples:**
```bash
# Load 10 records from the default record set
biotope annotate load \
  --jsonld metadata.json \
  --record-set samples

# Load 50 records from a specific record set
biotope annotate load \
  --jsonld metadata.json \
  --record-set measurements \
  --num-records 50
```

**Output:**
```
Record 1: {'patient_id': 'P001', 'gene_expression': [0.1, 0.2, 0.3]}
Record 2: {'patient_id': 'P002', 'gene_expression': [0.4, 0.5, 0.6]}
...
Loaded 10 records from record set 'samples'
```

## Metadata Pre-fill Priority

When pre-filling metadata, the following priority order is used:

1. **Command-line prefill**: Metadata provided via `--prefill-metadata`
2. **Project metadata**: Metadata from `.biotope/config/biotope.yaml`
3. **Default values**: Built-in defaults for required fields

This allows you to override project-level metadata when needed while still benefiting from the convenience of pre-filled values.

## Croissant ML Format

Biotope uses the Croissant ML metadata format for dataset annotations. This format provides:

- **Standardized structure**: Consistent metadata across different datasets
- **Rich annotations**: Support for complex metadata relationships
- **Validation**: Built-in validation of metadata structure
- **Interoperability**: Compatible with other ML metadata tools

### Key Croissant ML Concepts

1. **Dataset**: The top-level container for all metadata
2. **Distribution**: How the dataset is distributed (FileObject, FileSet)
3. **RecordSet**: Structure of data records
4. **Field**: Individual data fields with types and constraints
5. **Context**: JSON-LD context for semantic meaning

### Scientific Metadata Fields

Biotope includes additional scientific metadata fields:

- `cr:accessRestrictions`: Data access restrictions
- `cr:legalObligations`: Legal requirements for data usage
- `cr:collaborationPartner`: Collaboration partner information
- `cr:projectName`: Project name for context

## Configuration

Project metadata is managed through the `biotope config` command:

```bash
# Set project metadata for pre-filling
biotope config set-project-metadata

# View current project metadata
biotope config show-project-metadata
```

## Best Practices

1. **Use Interactive Mode**: For most use cases, `biotope annotate interactive` provides the best user experience
2. **Set Project Metadata**: Configure project-level metadata early for consistent annotations
3. **Validate Regularly**: Use `biotope annotate validate` to ensure metadata quality
4. **Use Descriptive Names**: Choose clear, descriptive dataset names
5. **Include All Required Fields**: Ensure all required metadata fields are completed
6. **Test with Load**: Use `biotope annotate load` to verify metadata works with actual data

## Integration with Git Workflow

The annotate commands integrate seamlessly with biotope's Git workflow:

```bash
# Add files to staging
biotope add data/raw/experiment.csv

# Create metadata interactively
biotope annotate interactive --staged

# Validate the metadata
biotope annotate validate --jsonld .biotope/datasets/experiment.csv.jsonld

# Commit the changes
biotope commit -m "Add experiment dataset with metadata"
```

## Troubleshooting

### Validation Errors
- Ensure all required fields are present
- Check that field values meet validation requirements
- Verify JSON-LD syntax is correct

### Load Errors
- Ensure the record set name exists in the metadata
- Check that the data source is accessible
- Verify the metadata file is valid

### Interactive Mode Issues
- Make sure you're in a biotope project directory
- Check that files are properly staged with `biotope add`
- Verify project metadata is configured if using pre-fill

::: biotope.commands.annotate