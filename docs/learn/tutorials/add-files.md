# Adding Files to Your Biotope Project

The `biotope add` command is your first step in managing data files with biotope. It prepares your files for metadata creation and version control. This tutorial will show you how to use it effectively.

## Prerequisites

Before you start, make sure you have:

1. **A biotope project initialized**: Run `biotope init` if you haven't already
2. **Git repository**: Your project should be a Git repository (biotope init can set this up)
3. **Data files**: Some files you want to track

## Basic Usage

### Adding a Single File

The simplest way to add a file is to provide its path:

```bash
biotope add data/raw/experiment.csv
```

This will:
- Calculate a SHA256 checksum for data integrity
- Create a basic metadata file in `.biotope/datasets/`
- Stage the metadata changes in Git
- Show you what happened

### Adding Remote Files

If you want to add files from a URL, use `biotope get` instead:

```bash
biotope get https://example.com/data/experiment.csv
```

This downloads the file and stages it for metadata creation, just like `biotope add`. The workflow after downloading is the same: check status, annotate, and commit.

### Adding Multiple Files

You can add several files at once:

```bash
biotope add data/raw/experiment1.csv data/raw/experiment2.csv data/raw/experiment3.csv
```

### Adding Entire Directories

To add all files in a directory, use the `--recursive` flag:

```bash
biotope add data/raw/ --recursive
```

This will add all files in `data/raw/` and any subdirectories.

## Understanding the Output

When you run `biotope add`, you'll see output like this:

```
📁 Added data/raw/experiment.csv (SHA256: e471e5fc...)

✅ Added 1 file(s) to biotope project:
  + data/raw/experiment.csv

💡 Next steps:
  1. Run 'biotope status' to see staged files
  2. Run 'biotope annotate interactive --staged' to create metadata
  3. Run 'biotope commit -m "message"' to save changes

💡 For incomplete annotations:
  1. Run 'biotope status' to see which files need annotation
  2. Run 'biotope annotate interactive --incomplete' to complete them
```

This tells you:
- Which files were successfully added
- Their checksums for data integrity
- What to do next in your workflow

**Important**: The data file itself is not added to Git - only the metadata is tracked. The `data/` directory is excluded from Git via `.gitignore` to keep repositories small and focused on metadata.

## Working with Different Path Types

### Relative Paths (Recommended)

Relative paths are preferred for better portability:

```bash
# From your project root
biotope add data/raw/experiment.csv
biotope add ./data/raw/experiment.csv

# From a subdirectory
cd data/raw/
biotope add experiment.csv
```

### Absolute Paths

You can also use absolute paths:

```bash
biotope add /Users/username/project/data/raw/experiment.csv
```

### Paths with Spaces

For files with spaces in their names, use quotes:

```bash
biotope add "data/raw/my experiment data.csv"
```

## Handling Common Scenarios

### Adding Already Tracked Files

If you try to add a file that's already tracked, you'll see:

```
⚠️  File 'data/raw/experiment.csv' already tracked (use --force to override)
```

To force add it anyway (useful if the file has changed):

```bash
biotope add data/raw/experiment.csv --force
```

### Adding Directories Without Recursive Flag

If you try to add a directory without `--recursive`:

```
⚠️  Skipping directory 'data/raw/' (use --recursive to add contents)
```

To add the directory contents:

```bash
biotope add data/raw/ --recursive
```

### Mixed Results

When adding multiple files, some might succeed and others might fail:

```
📁 Added data/raw/experiment1.csv (SHA256: abc123...)
⚠️  File 'data/raw/experiment2.csv' already tracked (use --force to override)

✅ Added 1 file(s) to biotope project:
  + data/raw/experiment1.csv

⚠️  Skipped 1 file(s):
  - data/raw/experiment2.csv
```

## Organizing Your Data

### Recommended Directory Structure

```
your-project/
├── data/
│   ├── raw/           # Original data files
│   │   ├── experiment1/
│   │   └── experiment2/
│   └── processed/     # Processed data files
├── .biotope/          # Metadata (auto-created)
└── .git/              # Git repository
```

### Adding Different Data Types

```bash
# Add raw data
biotope add data/raw/ --recursive

# Add processed data
biotope add data/processed/ --recursive

# Add specific file types
biotope add data/raw/*.csv
biotope add data/raw/*.fasta
```

## Integration with Other Commands

### Check What Was Added

After adding files, check their status:

```bash
biotope status
```

This shows you what metadata files are staged for commit.

### Create Detailed Metadata

The basic metadata created by `add` is minimal. Enhance it:

```bash
biotope annotate interactive --staged
```

This opens an interactive session to add detailed metadata.

### Commit Your Changes

Once you're satisfied with the metadata:

```bash
biotope commit -m "Add experiment dataset with 24 samples"
```

### Verify Data Integrity

Later, you can verify your files haven't been corrupted:

```bash
biotope check-data
```

## Git and Data Files

### Understanding the Separation

Biotope separates data files from Git tracking:

- **Data files**: Stored in `data/` directory, excluded from Git via `.gitignore`
- **Metadata**: Stored in `.biotope/datasets/`, tracked by Git
- **Checksums**: Embedded in metadata to ensure data integrity

### Benefits of This Approach

```bash
# Clean Git status (no data files cluttering output)
git status

# Only metadata changes appear in history
git log --oneline

# Small repository size (no large data files)
du -sh .git

# Easy collaboration (share metadata, not data)
git push origin main
```

### Working with Data Files

Even though data files aren't in Git, biotope still tracks them:

```bash
# Add a file (creates metadata, doesn't add to Git)
biotope add data/raw/experiment.csv

# Check what's tracked (metadata only)
biotope status

# Verify data integrity
biotope check-data

# See all tracked metadata files
git ls-files .biotope/
```

## Best Practices

### 1. Use Relative Paths

Relative paths make your project more portable:

```bash
# Good
biotope add data/raw/experiment.csv

# Avoid
biotope add /absolute/path/to/experiment.csv
```

### 2. Organize Your Data

Keep your data organized in logical directories:

```bash
data/
├── raw/
│   ├── experiment_2024_01/
│   └── experiment_2024_02/
└── processed/
    └── combined_results/
```

### 3. Add Files Incrementally

Add files as you work with them rather than all at once:

```bash
# Add files as you create them
biotope add data/raw/new_experiment.csv
biotope annotate interactive --staged
biotope commit -m "Add new experiment data"
```

### 4. Use Descriptive Commit Messages

When you commit after adding files:

```bash
# Good
biotope commit -m "Add RNA-seq dataset: 24 samples, 3 conditions"

# Better
biotope commit -m "Add RNA-seq dataset: 24 samples, 3 conditions, QC passed, ready for analysis"
```

## Troubleshooting

### "Not in a biotope project"

```bash
❌ Not in a biotope project. Run 'biotope init' first.
```

**Solution**: Run `biotope init` to initialize a biotope project.

### "Not in a Git repository"

```bash
❌ Not in a Git repository. Initialize Git first with 'git init'.
```

**Solution**: Initialize Git in your project directory:

```bash
git init
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### "File already tracked"

```bash
⚠️  File 'data/raw/experiment.csv' already tracked (use --force to override)
```

**Solution**: Use `--force` if you want to update the file's metadata:

```bash
biotope add data/raw/experiment.csv --force
```

### "Path does not exist"

```bash
❌ Path 'data/raw/experiment.csv' does not exist.
```

**Solution**: Check the file path and make sure the file exists.

## Related Commands

- **[Downloading Files](get-files.md)**: Learn how to download and stage files from URLs
- **[Annotating Data](annotate-omics.md)**: Learn how to create detailed metadata for your data
- **[Project Status](git-integration.md)**: Learn how to check your project status and manage metadata

## Getting Help

For additional help, use:

```bash
biotope add --help
```

This will show all available options and usage examples. 