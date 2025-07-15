# Git Integration for Developers

This document explains the technical implementation of biotope's Git-on-Top strategy for metadata version control.

## Architecture Overview

Biotope implements a **Git-on-Top** strategy where all version control operations delegate to Git via `subprocess.run()` calls. No custom version control is implemented.

### Key Principles

1. **Git Wrapper Pattern**: All biotope commands wrap Git operations with metadata-specific logic
2. **No Custom Version Control**: Zero custom commit history, branching, or remote handling
3. **Separation of Concerns**: Data files in `data/`, metadata in `.biotope/datasets/`
4. **Croissant ML Integration**: Metadata follows Croissant ML standard with validation
5. **Project Metadata Management**: Project-level metadata stored in `.biotope/config/biotope.yaml` for annotation pre-fill

### Project Structure

```
your-project/
├── .git/                  # Git repository (handled by Git)
├── .biotope/              # Git-tracked metadata
│   ├── datasets/          # Croissant ML JSON-LD files
│   ├── config/            # Biotope configuration (Git-like approach)
│   │   └── biotope.yaml   # Consolidated configuration and project metadata
│   ├── workflows/         # Bioinformatics workflows
│   └── logs/              # Command execution logs
├── data/                  # Data files (not in Git)
│   ├── raw/
│   └── processed/
├── config/                # User configuration
├── schemas/               # Knowledge schemas
└── outputs/               # Generated outputs
```

## Implementation Details

### Core Commands

#### `biotope init` (`biotope/commands/init.py`)

```python
def _init_git_repo(directory: Path) -> None:
    """Initialize a Git repository in the directory."""
    subprocess.run(["git", "init"], cwd=directory, check=True)
    subprocess.run(["git", "add", "."], cwd=directory, check=True)
    subprocess.run(["git", "commit", "-m", "Initial biotope project setup"], cwd=directory, check=True)

def _collect_project_metadata() -> Dict:
    """Collect project-level metadata for annotation pre-fill."""
    metadata = {}
    if click.confirm("Would you like to collect project-level metadata for annotation pre-fill?"):
        metadata["description"] = click.prompt("Project description")
        metadata["url"] = click.prompt("Project URL")
        metadata["creator"] = {
            "name": click.prompt("Creator name"),
            "email": click.prompt("Creator email")
        }
        metadata["license"] = click.prompt("License")
        metadata["citation"] = click.prompt("Citation")
    return metadata

def _create_biotope_config(biotope_root: Path, config: Dict) -> None:
    """Create biotope configuration file with project metadata."""
    config_dir = biotope_root / ".biotope" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_data = {
        "project_name": config.get("project_name"),
        "git_integration": config.get("git_integration", True),
        "knowledge_graph": config.get("knowledge_graph", {}),
        "project_metadata": config.get("project_metadata", {}),
        "annotation_validation": config.get("annotation_validation", {})
    }
    
    with open(config_dir / "biotope.yaml", "w") as f:
        yaml.dump(config_data, f, default_flow_style=False)
```

- Creates `.biotope/` directory structure
- Initializes Git repository with `subprocess.run(["git", "init"])`
- Collects project-level metadata for annotation pre-fill
- Creates initial commit with project setup
- Conditionally shows output format selection only when knowledge graph is enabled

#### `biotope config` (`biotope/commands/config.py`)

```python
def set_project_metadata() -> None:
    """Set project-level metadata for annotation pre-fill."""
    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort
    
    config = load_biotope_config(biotope_root)
    project_metadata = config.get("project_metadata", {})
    
    # Interactive metadata collection
    project_metadata["description"] = click.prompt("Project description", default=project_metadata.get("description", ""))
    project_metadata["url"] = click.prompt("Project URL", default=project_metadata.get("url", ""))
    project_metadata["creator"] = {
        "name": click.prompt("Creator name", default=project_metadata.get("creator", {}).get("name", "")),
        "email": click.prompt("Creator email", default=project_metadata.get("creator", {}).get("email", ""))
    }
    project_metadata["license"] = click.prompt("License", default=project_metadata.get("license", ""))
    project_metadata["citation"] = click.prompt("Citation", default=project_metadata.get("citation", ""))
    
    # Update configuration
    config["project_metadata"] = project_metadata
    save_biotope_config(biotope_root, config)

def show_project_metadata() -> None:
    """Display current project-level metadata configuration."""
    biotope_root = find_biotope_root()
    if not biotope_root:
        click.echo("❌ Not in a biotope project. Run 'biotope init' first.")
        raise click.Abort
    
    config = load_biotope_config(biotope_root)
    project_metadata = config.get("project_metadata", {})
    
    console = Console()
    console.print("\n[bold blue]Project Metadata Configuration[/]")
    console.print(f"Description: {project_metadata.get('description', 'Not set')}")
    console.print(f"URL: {project_metadata.get('url', 'Not set')}")
    console.print(f"Creator: {project_metadata.get('creator', {}).get('name', 'Not set')} ({project_metadata.get('creator', {}).get('email', 'Not set')})")
    console.print(f"License: {project_metadata.get('license', 'Not set')}")
    console.print(f"Citation: {project_metadata.get('citation', 'Not set')}")
```

- Manages project-level metadata for annotation pre-fill
- Provides interactive metadata collection and display
- Stores metadata in `.biotope/config/biotope.yaml`

#### `biotope commit` (`biotope/commands/commit.py`)

```python
def _create_git_commit(biotope_root: Path, message: str, author: Optional[str], amend: bool) -> Optional[str]:
    """Create a Git commit for .biotope/ changes."""
    cmd = ["git", "commit"]
    if amend:
        cmd.append("--amend")
    if author:
        cmd.extend(["--author", author])
    cmd.extend(["-m", message])
    
    result = subprocess.run(cmd, cwd=biotope_root, capture_output=True, text=True, check=True)
    # Extract commit hash from output
```

- Validates Croissant ML metadata before committing
- Stages `.biotope/` directory with `git add .biotope/`
- Delegates actual commit to Git via `subprocess.run()`
- Supports standard Git options (`--amend`, `--author`)

#### `biotope status` (`biotope/commands/status.py`)

```python
def _get_git_status(biotope_root: Path, biotope_only: bool) -> Dict[str, List]:
    """Get Git status for .biotope/ directory."""
    cmd = ["git", "status", "--porcelain"]
    if biotope_only:
        cmd.append(".biotope/")
    
    result = subprocess.run(cmd, cwd=biotope_root, capture_output=True, text=True, check=True)
    # Parse Git's porcelain output format
```

- Uses `git status --porcelain` for machine-readable output
- Parses Git's status format (A, M, D, ??)
- Focuses on `.biotope/` directory changes

#### `biotope log` (`biotope/commands/log.py`)

```python
def _get_git_log(biotope_root: Path, max_count: Optional[int] = None, since: Optional[str] = None, author: Optional[str] = None, biotope_only: bool = False) -> List[Dict]:
    """Get Git log with optional filtering."""
    cmd = ["git", "log", "--pretty=format:%H|%an|%ad|%s", "--date=short"]
    if biotope_only:
        cmd.append("--")
        cmd.append(".biotope/")
    
    result = subprocess.run(cmd, cwd=biotope_root, capture_output=True, text=True, check=True)
    # Parse commit lines: hash|author|date|message
```

- Uses `git log` with custom format for parsing
- Supports all standard Git log options
- Filters for `.biotope/` directory with `-- .biotope/`

#### `biotope push` / `biotope pull` (`biotope/commands/push.py`, `biotope/commands/pull.py`)

```python
def _push_changes(biotope_root: Path, remote: str, branch: str, force: bool) -> bool:
    """Push changes to remote repository."""
    cmd = ["git", "push"]
    if force:
        cmd.append("--force")
    cmd.extend([remote, branch])
    
    result = subprocess.run(cmd, cwd=biotope_root, capture_output=True, text=True, check=True)
    return True
```

- Direct delegation to `git push` and `git pull`
- Supports standard Git options (`--force`, `--rebase`)
- No custom remote handling

### Supporting Commands

#### `biotope add` (`biotope/commands/add.py`)

```python
def _stage_git_changes(biotope_root: Path) -> None:
    """Stage .biotope/ changes in Git."""
    subprocess.run(["git", "add", ".biotope/"], cwd=biotope_root, check=True)
```

- Creates Croissant ML metadata files in `.biotope/datasets/`
- Calculates SHA256 checksums for data integrity
- Stages changes with `git add .biotope/`

#### `biotope check-data` (`biotope/commands/check_data.py`)

```python
def _get_recorded_checksum(file_path: Path, biotope_root: Path) -> Optional[str]:
    """Get the recorded checksum for a file."""
    datasets_dir = biotope_root / ".biotope" / "datasets"
    for dataset_file in datasets_dir.glob("*.jsonld"):
        with open(dataset_file) as f:
            metadata = json.load(f)
            for distribution in metadata.get("distribution", []):
                if distribution.get("@type") == "sc:FileObject":
                    content_url = distribution.get("contentUrl")
                    if content_url and (biotope_root / content_url) == file_path:
                        return distribution.get("sha256")
```

- Reads checksums from Croissant ML metadata files
- Validates data integrity against recorded checksums
- No version control functionality

## Project Metadata Integration

### Configuration Management

Project metadata is managed through a centralized configuration system:

```python
def load_biotope_config(biotope_root: Path) -> Dict:
    """Load biotope configuration with project metadata."""
    config_path = biotope_root / ".biotope" / "config" / "biotope.yaml"
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except (yaml.YAMLError, IOError):
        return {}
    
    return config

def save_biotope_config(biotope_root: Path, config: Dict) -> None:
    """Save biotope configuration with project metadata."""
    config_path = biotope_root / ".biotope" / "config" / "biotope.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
```

### Annotation Pre-fill Integration

The annotation system integrates project metadata for pre-filling:

```python
def load_project_metadata(biotope_root: Path) -> Dict:
    """Load project-level metadata from biotope configuration for pre-filling annotations."""
    config_path = biotope_root / ".biotope" / "config" / "biotope.yaml"
    if not config_path.exists():
        return {}
    
    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    except (yaml.YAMLError, IOError):
        return {}
    
    # Extract project metadata from configuration
    project_metadata = config.get("project_metadata", {})
    
    # Convert to Croissant format for pre-filling
    croissant_metadata = {}
    
    if project_metadata.get("description"):
        croissant_metadata["description"] = project_metadata["description"]
    if project_metadata.get("url"):
        croissant_metadata["url"] = project_metadata["url"]
    if project_metadata.get("creator"):
        croissant_metadata["creator"] = project_metadata["creator"]
    if project_metadata.get("license"):
        croissant_metadata["license"] = project_metadata["license"]
    if project_metadata.get("citation"):
        croissant_metadata["citation"] = project_metadata["citation"]
    
    return croissant_metadata
```

### Configuration File Structure

The `.biotope/config/biotope.yaml` file structure (Git-like approach):

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

# Project information (consolidated internal metadata)
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
  remote_config:
    url: "https://cluster.example.com/validation.yaml"
    cache_duration: 3600
    fallback: true
```

## Git Integration Patterns

### Common Helper Functions

All commands use these shared helper functions:

```python
def _is_git_repo(directory: Path) -> bool:
    """Check if directory is a Git repository."""
    try:
        result = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=directory, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def find_biotope_root() -> Optional[Path]:
    """Find the biotope project root directory."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".biotope").exists():
            return current
        current = current.parent
    return None
```

### Error Handling

All commands follow consistent error handling:

```python
try:
    result = subprocess.run(cmd, cwd=biotope_root, capture_output=True, text=True, check=True)
    return result.stdout.strip()
except subprocess.CalledProcessError as e:
    click.echo(f"❌ Git error: {e}")
    if e.stderr:
        click.echo(f"Error details: {e.stderr}")
    return None
```

### Metadata Validation

All metadata is validated against the Croissant ML schema before being committed. The validation process checks:

1. **Required Fields**: Ensures all minimum required fields are present
2. **Field Types**: Validates data types match expected schemas
3. **Field Constraints**: Checks length, format, and content requirements
4. **Schema Compliance**: Ensures metadata follows Croissant ML standards

#### Remote Validation Configuration

Biotope supports remote validation configurations to enforce institutional or cluster-wide policies. This allows administrators to maintain centralized validation requirements that are automatically applied to all projects.

##### Architecture

```python
def load_biotope_config(biotope_root: Path) -> Dict:
    """Load biotope configuration with remote validation support."""
    config = load_local_config(biotope_root)
    
    # Check for remote validation configuration
    remote_config = config.get("annotation_validation", {}).get("remote_config", {})
    if remote_config and remote_config.get("url"):
        remote_validation = _load_remote_validation_config(remote_config, biotope_root)
        if remote_validation:
            # Merge remote config with local config (local takes precedence)
            merged_validation = _merge_validation_configs(remote_validation, validation_config)
            config["annotation_validation"] = merged_validation
    
    return config
```

##### Configuration Structure

```yaml
# .biotope/config/biotope.yaml
annotation_validation:
  enabled: true
  remote_config:
    url: "https://cluster.example.com/biotope-validation.yaml"
    cache_duration: 3600  # seconds
    fallback_to_local: true
  # Local overrides (optional)
  minimum_required_fields: ["name", "description", "creator"]
```

##### Remote Configuration Format

```yaml
# https://cluster.example.com/biotope-validation.yaml
annotation_validation:
  enabled: true
  minimum_required_fields:
    - name
    - description
    - creator
    - dateCreated
    - distribution
    - license
  field_validation:
    name:
      type: string
      min_length: 1
    description:
      type: string
      min_length: 10
    creator:
      type: object
      required_keys: [name]
    dateCreated:
      type: string
      format: date
    distribution:
      type: array
      min_length: 1
    license:
      type: string
      min_length: 5
```

##### Caching Strategy

Remote configurations are cached locally to improve performance and enable offline operation:

```python
def _load_remote_validation_config(remote_config: Dict, biotope_root: Path) -> Optional[Dict]:
    """Load validation configuration from a remote URL with caching."""
    url = remote_config["url"]
    cache_duration = remote_config.get("cache_duration", 3600)
    
    # Check cache first
    cache_file = _get_cache_file_path(url, biotope_root)
    if cache_file.exists():
        cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if cache_age.total_seconds() < cache_duration:
            return load_cached_config(cache_file)
    
    # Fetch from remote and cache
    remote_config_data = fetch_remote_config(url)
    cache_remote_config(remote_config_data, cache_file)
    return remote_config_data
```

##### Configuration Merging

Local configurations can extend or override remote requirements:

```python
def _merge_validation_configs(remote_config: Dict, local_config: Dict) -> Dict:
    """Merge remote and local validation configurations."""
    merged = remote_config.copy()
    
    # Merge required fields (union)
    remote_fields = set(remote_config.get("minimum_required_fields", []))
    local_fields = set(local_config.get("minimum_required_fields", []))
    merged["minimum_required_fields"] = list(remote_fields | local_fields)
    
    # Merge field validation (local overrides remote)
    remote_validation = remote_config.get("field_validation", {})
    local_validation = local_config.get("field_validation", {})
    merged["field_validation"] = {**remote_validation, **local_validation}
    
    return merged
```

##### CLI Commands

```bash
# Set remote validation URL
biotope config set-remote-validation --url https://cluster.example.com/validation.yaml

# Show remote validation status
biotope config show-remote-validation

# Clear validation cache
biotope config clear-validation-cache

# Remove remote validation
biotope config remove-remote-validation
```

##### Use Cases

1. **Institutional Clusters**: Enforce consistent metadata standards across all research projects
2. **Multi-site Collaborations**: Share validation requirements between institutions
3. **Compliance Requirements**: Ensure datasets meet regulatory or funding requirements
4. **Quality Assurance**: Maintain high metadata quality standards

##### Implementation Notes

- **Fallback Behavior**: Projects can fall back to local configuration if remote is unavailable
- **Cache Management**: Automatic cache invalidation based on configurable duration
- **Security**: HTTPS URLs recommended for production use
- **Performance**: Caching reduces network overhead and improves reliability 

## Croissant ML Integration

### Metadata Structure

All metadata follows Croissant ML standard:

```json
{
  "@context": {"@vocab": "https://schema.org/"},
  "@type": "Dataset",
  "name": "experiment-dataset",
  "description": "RNA-seq experiment data",
  "distribution": [
    {
      "@type": "sc:FileObject",
      "@id": "file_abc123",
      "name": "experiment.csv",
      "contentUrl": "data/raw/experiment.csv",
      "sha256": "abc123...",
      "contentSize": 1024
    }
  ]
}
```

### Data Integrity

- SHA256 checksums embedded in metadata
- Automatic validation before commits
- Data integrity checking via `biotope check-data`

## Testing

### Test Structure

Tests verify Git integration without mocking Git:

```python
def test_commit_success(self, runner, biotope_project):
    """Test successful commit."""
    with patch("biotope.commands.commit.find_biotope_root", return_value=biotope_project):
        # Create a change
        with open(biotope_project / ".biotope" / "datasets" / "new.jsonld", "w") as f:
            json.dump({"name": "new-dataset"}, f)
        
        result = runner.invoke(commit, ["-m", "Add new dataset"])
        assert result.exit_code == 0
        assert "Commit" in result.output
```

### Git Command Testing

Tests use actual Git commands:

```python
# Initialize Git repository
subprocess.run(["git", "init"], cwd=tmp_path, check=True)
subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True)
```

## Configuration

### Biotope Configuration

`.biotope/config/biotope.yaml`:

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
```

### Git Configuration

Standard Git configuration applies - no biotope-specific Git config.

## Security Considerations

- No custom version control reduces attack surface
- Git's battle-tested security model applies
- Checksums provide data integrity verification
- Metadata validation prevents malformed commits

## Performance

- Git operations are delegated to native Git binary
- No custom parsing or storage overhead
- Metadata files are small JSON-LD files
- Checksum calculation only on file changes

## Future Enhancements

Planned improvements while maintaining Git-on-Top:

- Enhanced Croissant ML validation
- Metadata conflict resolution tools
- Integration with external metadata repositories
- Workflow automation features

## Conclusion

The Git-on-Top implementation provides:

- **Reliability**: Battle-tested Git infrastructure
- **Simplicity**: No custom version control complexity
- **Familiarity**: Standard Git workflows and tools
- **Maintainability**: Minimal custom code to maintain
- **Performance**: Native Git performance

This approach eliminates the need for custom version control while providing robust metadata management capabilities. 

# Developer & Admin Guide: Annotation Validation

This document describes the internals and configuration of the annotation validation system in Biotope (git-on-top mode).

## Configuration Structure

Annotation validation is configured in `.biotope/config/biotope.yaml` under the `annotation_validation` key:

```yaml
annotation_validation:
  enabled: true
  minimum_required_fields:
    - name
    - description
    - creator
    - dateCreated
    - distribution
  field_validation:
    name:
      type: string
      min_length: 1
    description:
      type: string
      min_length: 10
    creator:
      type: object
      required_keys: [name]
    dateCreated:
      type: string
      format: date
    distribution:
      type: array
      min_length: 1
```

- **enabled**: Toggle validation on/off.
- **minimum_required_fields**: List of fields that must be present in each metadata file.
- **field_validation**: Per-field validation rules (type, min_length, required_keys, etc).

## Validation Logic

Validation is implemented in `biotope/validation.py`:
- `is_metadata_annotated(metadata, config)` checks if a metadata dict meets requirements.
- `_validate_field(value, field_name, validation_rules)` applies per-field rules.
- `get_annotation_status_for_files(biotope_root, file_paths)` returns annotation status for a list of files.

The system supports:
- Type checks (`string`, `object`, `array`)
- Minimum length for strings/arrays
- Required keys for objects
- ISO date format for date fields

## Extending Validation

To add new validation rules:
- Update the `field_validation` structure in the config (via CLI or manually).
- Extend `_validate_field` in `biotope/validation.py`