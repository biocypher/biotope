# Git Integration for Users

Biotope makes metadata version control simple by using Git under the hood. If you know Git, you already know how to use biotope's version control!

## Quick Start

Think of biotope as Git for your scientific metadata. The workflow is familiar:

```bash
# 1. Initialize your project
biotope init

# 2. Add your data files
biotope add data/raw/experiment.csv

# 3. Create metadata (like staging changes)
biotope annotate interactive --staged

# Or complete incomplete annotations
biotope annotate interactive --incomplete

# 4. Commit your metadata
biotope commit -m "Add RNA-seq dataset with quality metrics"

# 5. Share with others
biotope push
```

## How It Works

Biotope stores your metadata in a `.biotope/` folder that Git tracks automatically. Your data files stay in the `data/` folder (not in Git), but biotope keeps track of them through metadata.

```
your-project/
├── .biotope/              # Your metadata (tracked by Git)
│   └── datasets/          # Metadata files
├── data/                  # Your data files (not in Git)
│   ├── raw/
│   └── processed/
└── .git/                  # Git repository
```

## Commands You'll Use

### `biotope init`
Sets up your project and optionally initializes Git.

```bash
biotope init
# Follow the prompts to configure your project
```

### `biotope add`
Adds data files to your project and prepares them for metadata creation.

```bash
biotope add data/raw/experiment.csv
biotope add data/raw/ --recursive  # Add entire directory
```

### `biotope status`
Shows what metadata changes are ready to commit.

```bash
biotope status                    # See all changes
biotope status --biotope-only     # See only metadata changes
```

### `biotope commit`
Saves your metadata changes (just like `git commit`).

```bash
biotope commit -m "Add experiment dataset"
biotope commit -m "Update metadata" --author "Your Name <email@example.com>"
biotope commit -m "Fix typo" --amend  # Fix last commit
```

### `biotope log`
Shows your metadata history.

```bash
biotope log                       # Full history
biotope log --oneline             # One line per commit
biotope log -n 5                  # Last 5 commits
biotope log --since "2024-01-01"  # Commits since date
```

### `biotope push` / `biotope pull`
Share metadata with your team.

```bash
biotope push                      # Share your changes
biotope pull                      # Get latest changes from team
biotope pull --rebase             # Pull with rebase
```

### `biotope check-data`
Verify your data files haven't been corrupted.

```bash
biotope check-data                # Check all files
biotope check-data -f data/raw/experiment.csv  # Check specific file
```

## Your Git Knowledge Applies

Since biotope uses Git, all your Git skills work:

```bash
# Branching
git checkout -b new-experiment
biotope add data/raw/new-data.csv
biotope commit -m "Add new experiment"
git checkout main
git merge new-experiment

# Viewing changes
git diff .biotope/               # See metadata changes
git log -- .biotope/             # View metadata history

# Collaboration
git remote add origin https://github.com/team/project.git
biotope push
```

## Common Workflows

### Adding New Data

```bash
# 1. Add your data files
biotope add data/raw/new-experiment.csv

# 2. Create metadata
biotope annotate interactive --staged

# 3. Commit and share
biotope commit -m "Add new experiment: 24 samples, 3 conditions"
biotope push
```

### Updating Existing Metadata

```bash
# 1. Check what needs updating
biotope status

# 2. Edit metadata files or re-annotate
biotope annotate interactive -f data/raw/experiment.csv

# 3. Commit changes
biotope commit -m "Update experiment description and add QC metrics"
```

### Completing Incomplete Annotations

```bash
# 1. Check which files need annotation
biotope status

# 2. Complete annotations for all incomplete tracked files
biotope annotate interactive --incomplete

# 3. Commit the completed annotations
biotope commit -m "Complete metadata for all tracked datasets"
```

### Working with Your Team

```bash
# 1. Get latest changes
biotope pull

# 2. Make your changes
biotope add data/raw/my-experiment.csv
biotope annotate interactive --staged

# 3. Share your work
biotope commit -m "Add my experiment dataset"
biotope push
```

## Best Practices

### Commit Messages
Write clear, descriptive commit messages:

```bash
# Good
biotope commit -m "Add RNA-seq dataset with quality metrics"

# Better
biotope commit -m "Add RNA-seq dataset: 24 samples, 3 conditions, QC passed"
```

### Data Organization
Keep your data organized:

```
data/
├── raw/
│   ├── experiment_1/
│   │   ├── samples.csv
│   │   └── measurements.csv
│   └── experiment_2/
└── processed/
    └── combined_results.csv
```

### Regular Checks
- Run `biotope check-data` regularly to ensure data integrity
- Use `biotope status` before committing to see what's changing
- Keep metadata and data in sync

## Troubleshooting

### "Not in a Git repository"
```bash
# Initialize Git
git init
# Or run biotope init which offers Git initialization
```

### "No changes to commit"
```bash
# Check if files are staged
biotope status
# Stage changes if needed
git add .biotope/
```

### "Remote 'origin' not found"
```bash
# Add remote repository
git remote add origin https://github.com/username/repo.git
```

### Data integrity issues
```bash
# Check for corrupted files
biotope check-data
# Re-download or regenerate corrupted files
```

## What's Different from Git?

- **Focus**: Biotope focuses on metadata, not code
- **Validation**: Metadata is automatically validated before commits
- **Checksums**: Data integrity is tracked automatically
- **Croissant ML**: Metadata follows scientific standards

## What's the Same as Git?

- **Commands**: Same workflow (add, commit, push, pull)
- **Options**: Same flags and options work
- **Collaboration**: Same branching, merging, and remote workflows
- **History**: Same log, diff, and status functionality

That's it! Your Git knowledge transfers directly to biotope. The only difference is that you're versioning scientific metadata instead of code. 

## Annotation Validation and Status Reporting

Biotope now supports project-specific annotation requirements, allowing administrators to define what fields must be present in dataset metadata for it to be considered "annotated". This helps ensure data quality and consistency across your project.

### How Annotation Status Works

- The `biotope status` command now shows, for each tracked and staged dataset, whether it is considered annotated (✅) or not (⚠️), based on the current project requirements.
- The summary section reports how many datasets are annotated and how many are not.

### What is "Annotated"?

A dataset is considered annotated if its metadata file (in `.biotope/datasets/`) contains all required fields, and those fields meet the validation rules set by your project admin. By default, required fields include `name`, `description`, `creator`, `dateCreated`, and `distribution`, but this can be customized.

### Example: Status Output

```
$ biotope status

[bold blue]Biotope Project Status[/]
Project: my-biotope
Location: /path/to/project
Git Repository: ✅

[bold green]Changes to be committed:[/]
Status  File                              Annotated
A       .biotope/datasets/mydata.jsonld   ✅

[bold blue]Tracked Datasets:[/]
Dataset         Annotated   Status
mydata          ✅          Complete
rawdata         ⚠️          Incomplete (2 issues)

[bold]Summary:[/]
  Staged: 1 file(s) (1 annotated, 0 unannotated)
  Tracked datasets: 2 (1 annotated, 1 unannotated)
```

### Customizing Annotation Requirements

Admins can configure what fields are required and how they are validated using the `biotope config` command group.

#### Show Current Requirements

```
$ biotope config show-validation

[bold blue]Annotation Validation Configuration[/]
Enabled: ✅

[bold green]Required Fields:[/]
Field        Type      Validation Rules
name         string    min_length: 1
description  string    min_length: 10
creator      object    required_keys: name
dateCreated  string    format: date
distribution array     min_length: 1
```

#### Add a Required Field

```
$ biotope config set-validation --field license --type string --min-length 3
```

#### Remove a Required Field

```
$ biotope config remove-validation --field license
```

#### Enable/Disable Validation

```
$ biotope config toggle-validation --enabled
$ biotope config toggle-validation --disabled
```

#### Remote Validation Configuration

For institutional clusters or multi-site collaborations, you can use remote validation configurations to enforce consistent policies across all projects.

##### Set Remote Validation URL

```bash
# Set a remote validation configuration
$ biotope config set-remote-validation --url https://cluster.example.com/validation.yaml

# With custom cache duration (in seconds)
$ biotope config set-remote-validation --url https://cluster.example.com/validation.yaml --cache-duration 7200

# Disable fallback to local config if remote fails
$ biotope config set-remote-validation --url https://cluster.example.com/validation.yaml --no-fallback
```

##### Show Remote Validation Status

```bash
$ biotope config show-remote-validation
```

This shows:
- Remote URL and configuration
- Cache status and age
- Effective configuration (remote + local merged)

##### Clear Validation Cache

```bash
$ biotope config clear-validation-cache
```

##### Remove Remote Validation

```bash
$ biotope config remove-remote-validation
```

##### Example Remote Configuration

```yaml
# https://cluster.example.com/validation.yaml
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
    license:
      type: string
      min_length: 5
```

##### How Remote Validation Works

1. **Caching**: Remote configurations are cached locally for performance
2. **Merging**: Local configurations can extend or override remote requirements
3. **Fallback**: If remote is unavailable, falls back to local configuration
4. **Updates**: Cache is refreshed based on configurable duration

##### Use Cases

- **Institutional Clusters**: Enforce consistent metadata standards
- **Multi-site Collaborations**: Share validation requirements
- **Compliance**: Ensure datasets meet regulatory requirements
- **Quality Assurance**: Maintain high metadata quality standards

See also: [Admin documentation](git-integration-dev.md) for advanced configuration and developer details. 