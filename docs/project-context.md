# Project Context in Biotope

*How project context drives workflows, resource management, command behavior, and agentic behaviours*

## Overview

Biotope uses a **context-first approach** where each biotope project maintains its own configuration that drives the behavior of commands, resource management, and AI agents. This allows for seamless integration of different resource types (files, MCP servers, knowledge graph components) while ensuring that all software processes—from data annotation to knowledge extraction to agentic inference—are grounded in the project's scientific context and domain understanding.

## Project Context Philosophy

### Context-First Design Philosophy

Biotope embraces a **context-first approach** where project configuration drives not just resource management, but also the behavior of software processes and AI agents. This philosophy recognizes that:

- **Knowledge extraction** is domain-specific and requires contextual understanding
- **Agentic inference** on knowledge graphs depends on project context and goals
- **RAG (Retrieval-Augmented Generation)** systems need project-specific grounding
- **Scientific workflows** require consistent context across all tools and processes

The project context serves as the **semantic foundation** that informs how AI agents interpret data, which knowledge sources to prioritize, and how to structure reasoning about the project's domain.

### Unified Resource Management

Biotope treats all resources as part of a unified ecosystem within each project:

- **Data Files**: Local files with metadata annotations
- **MCP Servers**: Model Context Protocol servers for agentic workflows
- **Knowledge Graph Components**: BioCypher ecosystem components

### Context-Driven Configuration

Each biotope project maintains configuration that determines:

1. **Available Registries**: Which external registries to search
2. **Resource Preferences**: Default behaviors for different resource types
3. **Integration Settings**: How resources interact with each other
4. **Workflow Definitions**: Project-specific automation and pipelines
5. **AI Agent Behavior**: How knowledge extraction and inference are performed
6. **Domain Context**: Scientific domain, research goals, and methodology

## Project Configuration Structure

### Current vs Future Configuration

The project context approach builds on biotope's existing configuration structure while extending it for future registry integration. The current configuration includes:

**Current Configuration:**

- Data storage and file management
- Annotation validation rules
- Project metadata and information
- Checksum and staging settings

**Future Enhancements:**

- Registry integration for MCP servers and knowledge graphs
- Resource lifecycle management
- Multi-registry search and discovery
- Project-specific workflow definitions

### Core Configuration

```yaml
# .biotope/config/biotope.yaml
version: "1.0"                     # Biotope config file format version
croissant_schema_version: "1.0"    # Croissant ML schema version
default_metadata_template: "scientific"

# Data Storage Configuration
data_storage:
  type: "local"
  path: "data"

# Checksum and Staging
checksum_algorithm: "sha256"
auto_stage: true
commit_message_template: "Update metadata: {description}"

# Annotation Validation
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

# Project Information
project_info:
  name: "My Bioinformatics Project"
  created_at: "2024-01-15T10:30:00Z"
  biotope_version: "0.5.0"         # Version of biotope software used
  last_modified: "2024-01-15T10:30:00Z"
  builds: []
  knowledge_sources: []

# Project Metadata (for pre-filling annotations)
project_metadata:
  citation: "Please cite this dataset as: {name} ({year})"
  license: "https://creativecommons.org/licenses/by/4.0/"
  creator: "researcher@example.com"

# Registry Configuration (Future Enhancement)
registries:
  mcp:
    url: "https://biocontext.ai/registry.json"
    cache_duration: 3600
  kg:
    url: "https://kg-registry.biocypher.org/registry.json"
    cache_duration: 3600

# Resource Management (Future Enhancement)
resource_management:
  auto_detect_types: true
  default_clone_location: ".biotope/resources/"
  git_submodules: false
  
# MCP Server Configuration (Future Enhancement)
mcp_servers:
  default_environment: "python"
  auto_install_dependencies: true
  port_range: [3000, 3100]
  lifecycle_management: true

# Knowledge Graph Configuration (Future Enhancement)
knowledge_graphs:
  default_schema: "biocypher"
  auto_build: false
  integration_mode: "modular"
```

## Command Behavior Driven by Context

### Seamless Resource Discovery

```bash
# Search across all configured registries
biotope search "PubMed"
# Returns: MCP servers, KG components, datasets, workflows

# Auto-detection based on project context
biotope add "genomoncology/biomcp"
# Detects as MCP server, uses project MCP settings
```

### Context-Aware Status

```bash
# Shows status of all resource types in project
biotope status
# Displays: files, MCP servers, KG components, workflows

# Filter by resource type
biotope status --type mcp
biotope status --type kg
```

### Project-Specific Workflows

```bash
# Uses project-defined workflow
biotope workflow run "multi-omics-pipeline"
# Integrates: MCP servers, KG components, data files

# Project-specific validation
biotope validate
# Checks: data integrity, MCP connectivity, KG consistency

# Context-aware AI interactions
biotope chat "Analyze the proteomics data for IBD biomarkers"
# Uses: Project context, domain knowledge, relevant MCP servers

# Knowledge extraction with context
biotope extract "Extract gene-disease associations from literature"
# Grounded in: Project domain, methodology, research goals
```

## Registry Integration

### Multi-Registry Support

Biotope projects can integrate multiple registries:

```yaml
registries:
  mcp:
    url: "https://biocontext.ai/registry.json"
  kg:
    url: "https://kg-registry.biocypher.org/"
  workflow:
    url: "https://workflow-registry.example.com/"
```



## Resource Lifecycle Management

### MCP Server Lifecycle

```bash
# Project-context aware installation
biotope add mcp "genomoncology/biomcp"
# Uses project MCP settings for installation

# Lifecycle management
biotope mcp start "genomoncology/biomcp"
biotope mcp status
biotope mcp query "What is the most recent literature on IBD?"
biotope mcp stop "genomoncology/biomcp"
```

### Knowledge Graph Lifecycle

```bash
# Project-context aware integration
biotope add kg "biocypher/open-targets"
# Uses project KG settings for integration

# Graph management
biotope kg build
biotope kg validate
biotope kg query "Which targets are potentially tractable in IBD?"
```

## Project Context Benefits

### 1. Unified Experience

- Single command interface for all resource types
- Consistent metadata management across resources
- Unified version control and collaboration

### 2. Context-Aware Behavior

- Commands adapt to project configuration
- Resource discovery based on project needs
- Automated integration based on project context

### 3. Extensibility

- Easy to add new resource types
- Registry integration without command changes
- Project-specific workflows and automation

### 4. Collaboration

- Project context shared across team members
- Consistent resource management across environments
- Reproducible workflows and configurations

## Configuration Inheritance

### Global vs Project Settings

```yaml
# Global settings (user-wide) - Future Enhancement
~/.biotope/config.yaml:
  default_registries: ["mcp", "kg"]
  cache_duration: 3600

# Project settings (override global)
.biotope/config/biotope.yaml:
  # Current biotope configuration
  version: "1.0"
  croissant_schema_version: "1.0"
  data_storage:
    type: "local"
    path: "data"
  checksum_algorithm: "sha256"
  auto_stage: true
```

## Best Practices

### 1. Project-Specific Configuration

- Configure registries relevant to your domain
- Set resource preferences based on project needs
- Define workflows that match your research goals

### 2. Registry Selection

- Choose registries with high-quality, maintained resources
- Consider domain-specific registries for specialized needs
- Balance between comprehensive and focused registries

### 3. Resource Management

- Use consistent naming conventions across resource types
- Document project-specific workflows and integrations
- Regular validation and maintenance of integrated resources

### 4. Collaboration

- Share project configurations across team members
- Document project context decisions and rationale
- Version control project configurations alongside data

## Future Directions

### Planned Enhancements

1. **Workflow Registry**: Integration with workflow registries
2. **Dataset Registry**: Standardized dataset discovery and integration
3. **Plugin System**: Extensible resource type support
4. **Cloud Integration**: Cloud-native resource management
5. **AI-Assisted Configuration**: Intelligent project context suggestions

### Community Integration

- Registry contribution guidelines
- Project context sharing and templates
- Community-driven resource curation
- Standardized metadata schemas

This project context approach ensures that biotope remains a unified, extensible platform for scientific resource management while maintaining the flexibility needed for diverse research projects and workflows. 