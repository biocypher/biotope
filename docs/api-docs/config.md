# Biotope Config

!!! warning "Draft stage"

    Biotope is in draft stage. Functionality may be missing or incomplete.
    The API is subject to change.

## Overview

The `biotope config` command manages project configuration and metadata settings. It provides tools for setting up validation requirements, managing project metadata, and configuring remote validation services.

## Commands

### Project Metadata Management

#### `biotope config set-project-metadata`

Set project-level metadata that will be used to pre-fill annotation fields.

**Usage:**
```bash
biotope config set-project-metadata
```

**Interactive Prompts:**
- **Description**: Brief description of the project and its purpose
- **URL**: Project homepage, repository, or documentation URL
- **Creator Name**: Name of the project maintainer
- **Creator Email**: Email address of the project maintainer
- **License**: Data usage license (e.g., MIT, CC-BY, etc.)
- **Citation**: How to cite the project or dataset

**Example:**
```bash
$ biotope config set-project-metadata
Project description: A comprehensive dataset for protein structure analysis
Project URL: https://github.com/example/protein-data
Creator name: Dr. Jane Smith
Creator email: jane.smith@university.edu
License: MIT
Citation: Smith, J. et al. (2024). Protein Structure Dataset. Nature Data.
```

#### `biotope config show-project-metadata`

Display the current project-level metadata configuration.

**Usage:**
```bash
biotope config show-project-metadata
```

**Output:**
```
Project Metadata Configuration:
Description: A comprehensive dataset for protein structure analysis
URL: https://github.com/example/protein-data
Creator: Dr. Jane Smith (jane.smith@university.edu)
License: MIT
Citation: Smith, J. et al. (2024). Protein Structure Dataset. Nature Data.
```

### Validation Configuration

#### `biotope config show-validation`

Show current validation configuration and requirements.

#### `biotope config set-validation`

Set validation requirements for specific fields.

#### `biotope config remove-validation`

Remove validation requirements for specific fields.

#### `biotope config toggle-validation`

Enable or disable validation checking.

### Remote Validation Configuration

#### `biotope config set-remote-validation`

Configure remote validation service for cluster-wide policies.

#### `biotope config show-remote-validation`

Show remote validation configuration status.

#### `biotope config remove-remote-validation`

Remove remote validation configuration.

#### `biotope config clear-validation-cache`

Clear cached remote validation configuration.

## Configuration File Structure

Project metadata is stored in `.biotope/config/biotope.yaml`:

```yaml
project_name: "my-project"
git_integration: true

project_metadata:
  description: "Project description"
  url: "https://example.com/project"
  creator:
    name: "John Doe"
    email: "john@example.com"
  license: "MIT"
  citation: "Doe, J. (2024). Project Title. Journal Name."

annotation_validation:
  enabled: true
  fields:
    license:
      type: "string"
      required: true
      min_length: 3
  remote_config:
    url: "https://cluster.example.com/validation.yaml"
    cache_duration: 3600
    fallback: true
```

## Use Cases

### Setting Up Project Metadata

1. **During Initialization**: Set project metadata during `biotope init`
2. **After Initialization**: Use `biotope config set-project-metadata` to add or update metadata
3. **Team Projects**: Ensure all team members use consistent project metadata

### Annotation Workflow Integration

Project metadata automatically pre-fills annotation forms:

```bash
# Set project metadata once
biotope config set-project-metadata

# Use in annotation (metadata will be pre-filled)
biotope annotate interactive --staged
```

### Validation Configuration

Configure validation requirements for your project:

```bash
# Set required fields
biotope config set-validation --field license --type string --required

# Enable validation
biotope config toggle-validation --enabled

# Check configuration
biotope config show-validation
```

## Best Practices

1. **Set Project Metadata Early**: Configure project metadata during initialization or early in the project lifecycle
2. **Use Consistent Metadata**: Ensure all team members use the same project metadata for consistency
3. **Regular Updates**: Update project metadata when project details change
4. **Validation Requirements**: Set appropriate validation requirements for your use case
5. **Remote Validation**: Use remote validation for cluster-wide policy enforcement

::: biotope.commands.config 