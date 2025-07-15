# Downloading and Staging Files with `get`

The `get` command in Biotope provides a convenient way to download files from a URL and immediately stage them for metadata creation and version control. It integrates seamlessly with Biotope's git-on-top workflow. See also the [annotation tutorial](annotate-omics.md) for more information on annotating your data.

## Basic Usage

The simplest way to use the `get` command is to provide a URL:

```bash
biotope get https://raw.githubusercontent.com/biocypher/biotope/refs/heads/main/tests/example_gene_expression.csv
```

or 

```bash
biotope get https://raw.githubusercontent.com/biocypher/biotope/refs/heads/main/tests/example_protein_sequences.fasta
```

This will:
1. Download the file to the `data/raw` directory (or a custom location)
2. Add the file to your biotope project and stage it for metadata creation (using the same mechanism as `biotope add`)
3. Show you the next steps: annotate and commit

**Note:** The annotation process is now a separate, explicit step. After downloading, you should run `biotope annotate --staged` to create or complete the metadata, and then commit your changes.

**Important:** The downloaded data file is excluded from Git tracking via `.gitignore`. Only the metadata is version controlled, keeping repositories small and focused.

## Command Options

The `get` command supports the following options:

```bash
biotope get [OPTIONS] URL
```

### Available Options

- `--output-dir`, `-o`: Specify a custom directory for downloaded files (default: `data/raw`)
  ```bash
  biotope get https://example.com/data/file.txt --output-dir /path/to/dir
  ```
- `--no-add`: Download the file without adding it to the biotope project (advanced use)

## Download Locations

### Default Location

By default, files are downloaded to a `data/raw` directory in your current working directory:

```
your-project/
├── data/
│   ├── raw/           # Default download location
│   │   ├── file1.csv
│   │   └── file2.fasta
│   └── processed/
├── .biotope/
└── .git/
```

This aligns with the recommended project structure and makes it easy to organize your data files.

### Custom Location

You can specify a custom download location using the `--output-dir` option:

```bash
# Download to a specific directory
biotope get https://example.com/data/file.csv --output-dir ./data/processed

# Download to an absolute path
biotope get https://example.com/data/file.csv --output-dir /Users/username/project/data
```

### Recommended Organization

For better project organization, consider downloading files to appropriate subdirectories:

```bash
# Download to raw data directory (default)
biotope get https://example.com/data/experiment.csv

# Download to processed data directory
biotope get https://example.com/data/results.csv --output-dir ./data/processed

# Download to specific experiment directory
biotope get https://example.com/data/experiment.csv --output-dir ./data/raw/experiment_2024_01
```

## File Tracking and Moves

Biotope tracks files by their relative path from the project root. This means:

### How File Tracking Works

- Files are tracked using their relative path (e.g., `data/raw/experiment.csv`)
- The metadata stores this relative path in the `contentUrl` field
- Biotope can find files regardless of where you run commands from within the project

### Moving Files After Download

If you download a file and later want to reorganize your project structure:

1. **Move the file manually:**
   ```bash
   # Download to default location
   biotope get https://example.com/data/experiment.csv
   
   # Later, move to a better location
   mkdir -p data/raw/experiment_2024_01
   mv data/raw/experiment.csv data/raw/experiment_2024_01/
   ```

2. **Update the metadata:**
   ```bash
   # Check what's broken
   biotope check-data
   
   # Re-add the file in its new location
   biotope add data/raw/experiment_2024_01/experiment.csv --force
   ```

3. **Commit the changes:**
   ```bash
   biotope commit -m "Reorganize experiment data into subdirectory"
   ```

### Checking File Integrity

Use `biotope check-data` to verify that all tracked files are still accessible:

```bash
# Check all files
biotope check-data

# Check specific file
biotope check-data -f data/raw/experiment.csv
```

This will report:
- **Valid**: File exists and checksum matches
- **Missing**: File not found at recorded location
- **Corrupted**: File exists but checksum doesn't match
- **Untracked**: File not tracked in biotope

## Automatic Metadata Generation and Staging

When downloading a file, the `get` command automatically generates initial metadata in Croissant ML format and stages it in git. This includes:

- File identification (name, path, SHA256 hash)
- File type detection
- Source URL
- Creator information
- Creation date

The generated metadata follows the schema.org and Croissant ML standards, making it compatible with the rest of the Biotope ecosystem. Metadata is created in `.biotope/datasets/` and staged for commit.

### Example Generated Metadata

```json
{
    "name": "Dataset_file.txt",
    "description": "Dataset containing file downloaded from https://example.com/data/file.txt",
    "url": "https://example.com/data/file.txt",
    "creator": {
        "@type": "Person",
        "name": "username"
    },
    "dateCreated": "2024-03-21",
    "distribution": [
        {
            "@type": "sc:FileObject",
            "@id": "file_sha256hash",
            "name": "file.txt",
            "contentUrl": "data/raw/file.txt",
            "encodingFormat": "text/plain",
            "sha256": "sha256hash"
        }
    ]
}
```

## Next Steps: Annotate and Commit

After downloading and staging the file, continue with the standard git-on-top workflow:

1. **Check status:**
   ```bash
   biotope status
   ```
   This shows the staged file and its metadata status.

2. **Annotate the file:**
   ```bash
   biotope annotate interactive --staged
   ```
   This opens an interactive session to complete the metadata.

3. **Commit your changes:**
   ```bash
   biotope commit -m "Add new dataset from URL"
   ```

## Examples

### Download and Stage a CSV File

```bash
biotope get https://example.com/data/expression.csv
biotope status
biotope annotate interactive --staged
biotope commit -m "Add expression dataset"
```

### Download to a Specific Directory

```bash
biotope get https://example.com/data/expression.csv --output-dir ./data/processed
```

### Download Without Adding to Project

```bash
biotope get https://example.com/data/expression.csv --no-add
# Later, manually add the file
biotope add data/raw/expression.csv
```

## Integration with Other Commands

The `get` command integrates with the full git-on-top workflow:

- Use `biotope status` to see staged files and their annotation status
- Use `biotope annotate interactive --staged` to annotate all newly downloaded files
- Use `biotope commit` to save your changes
- Use `biotope check-data` to verify data integrity

## Troubleshooting

### Common Issues

1. **Download Fails**
   - Check your internet connection
   - Verify the URL is accessible
   - Ensure you have write permissions in the output directory

2. **Metadata Not Created**
   - Make sure you are in a biotope project and a git repository
   - Check for error messages in the output

3. **Annotation Fails**
   - Check if the file is corrupted
   - Verify you have sufficient disk space
   - Ensure you have the required permissions

4. **Metadata Issues**
   - Use `biotope annotate validate` to check metadata validity
   - Review the pre-filled metadata carefully
   - Make sure all required fields are filled

5. **File Not Found After Move**
   - Use `biotope check-data` to identify missing files
   - Re-add files in their new locations with `biotope add --force`
   - Commit the changes to update metadata

### Getting Help

For additional help, use:

```bash
biotope get --help
```

This will show all available options and usage examples. 