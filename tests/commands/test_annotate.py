"""Tests for the annotate command."""

import datetime
import getpass
import json
import csv
import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from biotope.commands.annotate import annotate, create, interactive, load, validate


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_metadata_file(tmp_path):
    """Create a sample metadata file for testing."""
    metadata_path = tmp_path / "metadata.json"

    # Create a sample metadata structure with proper Croissant format
    metadata = {
        "@context": {
            "@vocab": "https://schema.org/",
            "cr": "https://mlcommons.org/croissant/",
            "ml": "http://ml-schema.org/",
            "sc": "https://schema.org/",
        },
        "@type": "Dataset",
        "name": "Gene Expression Dataset",
        "description": "RNA-seq data from cancer patients",
        "url": "https://example.com/gene_data",
        "cr:projectName": "Cancer Genomics",
        "creator": {
            "@type": "Person",
            "name": "researcher@university.edu",
        },
        "dateCreated": "2025-08-27T13:37:12.651208+00:00",
        "cr:accessRestrictions": "Restricted to research use only",
        "encodingFormat": "CSV",
        "cr:legalObligations": "Data usage agreement required",
        "cr:collaborationPartner": "University Medical Center",
        "distribution": [
            {
                "@type": "cr:FileObject",
                "@id": "expression_data",
                "name": "expression_data.csv",
                "contentUrl": "https://example.com/gene_data/expression_data.csv",
                "encodingFormat": "text/csv",
                "sha256": "0b033707ea49365a5ffdd14615825511",
            },
        ],
        "cr:recordSet": [
            {
                "@type": "cr:RecordSet",
                "@id": "#samples",
                "name": "samples",
                "description": "Patient samples with gene expression data",
                "cr:field": [
                    {
                        "@type": "cr:Field",
                        "@id": "#samples/patient_id",
                        "name": "patient_id",
                        "description": "Unique identifier for each patient",
                        "dataType": "sc:Text",
                        "source": {
                            "fileObject": {"@id": "expression_data"},
                            "extract": {
                                "column": "patient_id",
                            },
                        },
                    },
                    {
                        "@type": "cr:Field",
                        "@id": "#samples/gene_expression",
                        "name": "gene_expression",
                        "description": "Normalized gene expression values",
                        "dataType": "sc:Float",
                        "repeated": True,
                        "source": {
                            "fileObject": {"@id": "expression_data"},
                            "extract": {
                                "column": "gene_expression",
                            },
                        },
                    },
                ],
            },
        ],
    }

    with Path(metadata_path).open("w") as f:
        json.dump(metadata, f)

    return metadata_path


def test_create_command_with_required_fields(runner, tmp_path):
    """Test creating a new metadata file with all required scientific metadata fields."""
    output_path = tmp_path / "output.json"

    # Run the create command with all required fields
    result = runner.invoke(
        create,
        [
            "--name",
            "Single-cell RNA-seq Dataset",
            "--description",
            "Single-cell RNA sequencing data from tumor microenvironment",
            "--data-source",
            "https://example.org/scRNA-seq",
            "--contact",
            "researcher@university.edu",
            "--date",
            "2023-05-20",
            "--access-restrictions",
            "Restricted to academic use",
            "--format",
            "H5AD",
            "--legal-obligations",
            "Citation required",
            "--collaboration-partner",
            "Cancer Research Institute",
            "--output",
            str(output_path),
        ],
    )

    # Check that the command executed successfully
    assert result.exit_code == 0
    assert f"Created Croissant metadata file at {output_path}" in result.output

    # Verify the file was created
    assert os.path.exists(output_path)

    # Check the content of the file
    with Path(output_path).open() as f:
        metadata = json.load(f)

    # Check basic fields
    assert metadata["name"] == "Single-cell RNA-seq Dataset"
    assert metadata["description"] == "Single-cell RNA sequencing data from tumor microenvironment"

    # Check required scientific metadata fields
    assert metadata["url"] == "https://example.org/scRNA-seq"  # Changed from dataSource
    assert metadata["creator"]["name"] == "researcher@university.edu"  # Changed from contactPerson
    assert metadata["dateCreated"] == "2023-05-20"  # Changed from creationDate
    assert metadata["cr:accessRestrictions"] == "Restricted to academic use"  # Added cr: prefix

    # Check optional fields
    assert metadata["encodingFormat"] == "H5AD"  # Changed from fileFormat
    assert metadata["cr:legalObligations"] == "Citation required"  # Added cr: prefix
    assert metadata["cr:collaborationPartner"] == "Cancer Research Institute"  # Added cr: prefix

    # Check for distribution array
    assert "distribution" in metadata
    assert isinstance(metadata["distribution"], list)


def test_create_command_with_defaults(runner, tmp_path):
    """Test creating a new metadata file with default values for some fields."""
    output_path = tmp_path / "output.json"
    today_date = datetime.datetime.now(tz=datetime.timezone.utc).date().isoformat()
    username = getpass.getuser()

    # Run the create command with minimal required fields
    result = runner.invoke(
        create,
        [
            "--name",
            "Proteomics Dataset",
            "--data-source",
            "https://example.org/proteomics",
            "--access-restrictions",
            "Public",
            "--output",
            str(output_path),
        ],
    )

    # Check that the command executed successfully
    assert result.exit_code == 0

    # Check the content of the file
    with Path(output_path).open() as f:
        metadata = json.load(f)

    # Check that defaults were applied
    assert metadata["name"] == "Proteomics Dataset"
    assert metadata["description"] == ""  # Default empty string
    assert metadata["url"] == "https://example.org/proteomics"  # Changed from dataSource
    assert metadata["creator"]["name"] == username  # Changed from contactPerson
    # Expect an ISO 8601 datetime with timezone; date portion should be today
    date_created_str = metadata["dateCreated"]
    assert "T" in date_created_str  # ensure datetime-like format
    dt = datetime.datetime.fromisoformat(date_created_str.replace("Z", "+00:00"))
    assert dt.tzinfo is not None and dt.utcoffset() == datetime.timedelta(0)
    assert dt.date().isoformat() == today_date
    assert metadata["cr:accessRestrictions"] == "Public"  # Added cr: prefix

    # Optional fields should not be present
    assert "encodingFormat" not in metadata  # Changed from fileFormat
    assert "cr:legalObligations" not in metadata  # Added cr: prefix
    assert "cr:collaborationPartner" not in metadata  # Added cr: prefix

    # Check for distribution array
    assert "distribution" in metadata
    assert isinstance(metadata["distribution"], list)
    assert len(metadata["distribution"]) == 0  # Should be empty by default


@mock.patch("subprocess.run")
def test_validate_command_success(mock_run, runner, sample_metadata_file):
    """Test validating a correctly formatted metadata file."""
    # Configure the mock to return a successful result
    mock_process = mock.Mock()
    mock_process.stdout = "Done"
    mock_process.stderr = ""
    mock_run.return_value = mock_process

    # Run the validate command
    result = runner.invoke(validate, ["--jsonld", str(sample_metadata_file)])

    # Check that the command executed successfully
    assert result.exit_code == 0
    assert "Validation successful!" in result.output

    # Verify that subprocess.run was called with the correct arguments
    mock_run.assert_called_once_with(
        ["mlcroissant", "validate", "--jsonld", str(sample_metadata_file)],
        capture_output=True,
        text=True,
        check=True,
    )


@mock.patch("subprocess.run")
def test_validate_command_failure(mock_run, runner, sample_metadata_file):
    """Test validating an incorrectly formatted metadata file."""
    # Configure the mock to raise an exception
    error_message = "Invalid schema: missing required field"
    mock_run.side_effect = subprocess.CalledProcessError(
        1,
        ["mlcroissant", "validate"],
        stderr=error_message,
    )

    # Run the validate command
    result = runner.invoke(validate, ["--jsonld", str(sample_metadata_file)])

    # Check that the command failed with the expected error
    assert result.exit_code == 1
    assert "Validation failed" in result.output
    assert error_message in result.output


@mock.patch("subprocess.run")
def test_load_command(mock_run, runner, sample_metadata_file):
    """Test loading records from a dataset."""
    # Configure the mock to return sample data
    sample_output = "\n".join(
        [f"Record {i + 1}: {{'patient_id': 'P{i}', 'gene_expression': [0.1, 0.2, 0.3]}}" for i in range(5)],
    )
    mock_process = mock.Mock()
    mock_process.stdout = sample_output
    mock_process.stderr = ""
    mock_run.return_value = mock_process

    # Run the load command
    result = runner.invoke(
        load,
        [
            "--jsonld",
            str(sample_metadata_file),
            "--record-set",
            "samples",
            "--num-records",
            "5",
        ],
    )

    # Check that the command executed successfully
    assert result.exit_code == 0
    assert "Loaded 5 records from record set 'samples'" in result.output

    # Verify that subprocess.run was called with the correct arguments
    mock_run.assert_called_once_with(
        [
            "mlcroissant",
            "load",
            "--jsonld",
            str(sample_metadata_file),
            "--record_set",
            "samples",
            "--num_records",
            "5",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    # Verify that the output was displayed
    assert sample_output in result.output


@mock.patch("click.prompt")
@mock.patch("rich.prompt.Prompt.ask")
@mock.patch("rich.prompt.Confirm.ask")
@mock.patch("getpass.getuser")
@mock.patch("datetime.date")
@mock.patch("click.confirm")
@mock.patch("rich.console.Console.print")
@mock.patch("rich.table.Table.add_row")
def test_interactive_command_with_scientific_fields(
    mock_table_add_row,
    mock_console_print,
    mock_click_confirm,
    mock_date,
    mock_getuser,
    mock_rich_confirm,
    mock_rich_prompt,
    mock_click_prompt,
    runner,
    tmp_path,
):
    """Test interactively creating a metadata file with scientific metadata fields."""
    mock_date.today.return_value = datetime.date(2023, 6, 15)
    mock_getuser.return_value = "researcher"

    # Configure the click.prompt mocks
    mock_click_prompt.side_effect = [
        "Proteomics Dataset",  # Dataset name
        "Mass spectrometry data from protein samples",  # Dataset description
        "https://example.org/proteomics",  # Data source URL
        "Protein Analysis",  # Project name
        "dr.researcher@university.edu",  # Contact person
        "2023-06-15",  # Creation date
        "mzML",  # File format
        "Data sharing agreement required",  # Legal obligations
        "Proteomics Center, University Hospital",  # Collaboration partner
        # New publication information fields
        "2023-06-15",  # Publication date
        "1.0",  # Version
        "https://creativecommons.org/licenses/by/4.0/",  # License URL
        "Please cite this dataset as: Proteomics Dataset (2023)",  # Citation text
        "protein_samples",  # Record set name
        "Protein samples with abundance measurements",  # Record set description
        "protein_id",  # Field name
        "Unique identifier for each protein",  # Field description
        "abundance",  # Field name
        "Normalized protein abundance",  # Field description
        str(tmp_path / "proteomics_dataset_metadata.json"),  # Output path (now uses default based on name)
    ]

    # Configure the rich.prompt.Prompt.ask mock for access restrictions
    mock_rich_prompt.side_effect = [
        "Restricted to project members",  # Access restrictions description
    ]

    # Configure the rich.prompt.Confirm.ask mock
    mock_rich_confirm.side_effect = [
        True,  # Has access restrictions
    ]

    # Configure the click.confirm mock
    mock_click_confirm.side_effect = [
        False,  # Would you like to add file resources? (No)
        True,  # Would you like to add a record set?
        False,  # Would you like to specify a data type for the record set? (No)
        True,  # Would you like to add fields to this record set?
        False,  # Would you like to specify a data type for the field? (No)
        False,  # Would you like to specify a data source for the field? (No)
        False,  # Is this a repeated field? (No)
        False,  # Does this field reference another field? (No)
        True,  # Add another field?
        False,  # Would you like to specify a data type for the field? (No)
        False,  # Would you like to specify a data source for the field? (No)
        False,  # Is this a repeated field? (No)
        False,  # Does this field reference another field? (No)
        False,  # Add another field?
        False,  # Would you like to specify key fields? (No)
        False,  # Add another record set?
    ]

    # Run the interactive command
    result = runner.invoke(interactive)

    # Check that the command executed successfully
    assert result.exit_code == 0

    # Verify the expected prompts were made
    assert mock_click_prompt.call_count == 20  # Updated count to include new prompts
    assert mock_rich_prompt.call_count == 1
    assert mock_rich_confirm.call_count == 1
    assert mock_click_confirm.call_count >= 5  # Now we have more confirmations for the enhanced features

    # Verify that Rich console methods were called (we don't need to check exact calls)
    assert mock_console_print.called
    assert mock_table_add_row.called

    # Check for success message - we can't check the exact format with Rich
    # but we can check that the output path is in the result
    expected_output_path = str(tmp_path / "proteomics_dataset_metadata.json")

    # Verify the file was created and contains the expected content
    assert Path(expected_output_path).exists()
    with Path(expected_output_path).open() as f:
        metadata = json.load(f)

    # Check that all the scientific metadata fields are present with updated structure
    assert metadata["name"] == "Proteomics Dataset"
    assert metadata["description"] == "Mass spectrometry data from protein samples"
    assert metadata["url"] == "https://example.org/proteomics"  # Changed from dataSource
    assert metadata["cr:projectName"] == "Protein Analysis"  # Added cr: prefix
    assert metadata["creator"]["name"] == "dr.researcher@university.edu"  # Changed structure
    assert metadata["dateCreated"] == "2023-06-15"  # Changed from creationDate
    assert metadata["cr:accessRestrictions"] == "Restricted to project members"  # Added cr: prefix
    assert metadata["encodingFormat"] == "mzML"  # Changed from fileFormat
    assert metadata["cr:legalObligations"] == "Data sharing agreement required"  # Added cr: prefix
    assert metadata["cr:collaborationPartner"] == "Proteomics Center, University Hospital"  # Added cr: prefix

    # Check new publication fields
    assert metadata["datePublished"] == "2023-06-15"
    assert metadata["version"] == "1.0"
    assert metadata["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert metadata["citation"] == "Please cite this dataset as: Proteomics Dataset (2023)"

    # Check for distribution array
    assert "distribution" in metadata
    assert isinstance(metadata["distribution"], list)

    # Check record set structure
    assert "cr:recordSet" in metadata
    assert len(metadata["cr:recordSet"]) > 0
    record_set = metadata["cr:recordSet"][0]
    assert record_set["@type"] == "cr:RecordSet"
    assert record_set["@id"] == "#protein_samples"
    assert "cr:field" in record_set
    assert len(record_set["cr:field"]) == 2

    # Check field structure
    field1 = record_set["cr:field"][0]
    assert field1["@type"] == "cr:Field"
    assert field1["@id"] == "#protein_samples/protein_id"
    assert field1["name"] == "protein_id"

    field2 = record_set["cr:field"][1]
    assert field2["@type"] == "cr:Field"
    assert field2["@id"] == "#protein_samples/abundance"
    assert field2["name"] == "abundance"


def test_annotate_group(runner):
    """Test the annotate command group."""
    # Run the annotate command without subcommands to see help
    result = runner.invoke(annotate)

    # Check that the command returns exit code 2 (indicating subcommand required)
    assert result.exit_code == 2

    # Verify that the help text includes all subcommands
    assert "create" in result.output
    assert "validate" in result.output
    assert "load" in result.output
    assert "interactive" in result.output

    # Check that the description mentions Croissant format
    assert "Croissant format" in result.output


@mock.patch("subprocess.run")
def test_complex_metadata_validity(mock_run, runner, tmp_path):
    """Test that complex metadata with record sets and file objects is valid."""
    # Create a complex metadata file directly
    metadata_path = tmp_path / "complex_metadata.json"

    # Create a more complex metadata structure with file objects and record sets
    metadata = {
        "@context": {
            "@vocab": "https://schema.org/",
            "cr": "https://mlcommons.org/croissant/",
            "ml": "http://ml-schema.org/",
            "sc": "https://schema.org/",
        },
        "@type": "Dataset",
        "name": "Complex Test Dataset",
        "description": "A dataset with multiple file objects and record sets",
        "url": "https://example.org/complex-data",
        "creator": {
            "@type": "Person",
            "name": "complex@example.org",
        },
        "dateCreated": "2023-09-01",
        "cr:accessRestrictions": "Academic use only",
        "encodingFormat": "Mixed",
        "distribution": [
            {
                "@type": "cr:FileObject",
                "@id": "data_csv",
                "name": "data.csv",
                "contentUrl": "https://example.org/complex-data/data.csv",
                "encodingFormat": "text/csv",
            },
            {
                "@type": "cr:FileObject",
                "@id": "metadata_json",
                "name": "metadata.json",
                "contentUrl": "https://example.org/complex-data/metadata.json",
                "encodingFormat": "application/json",
            },
            {
                "@type": "cr:FileSet",
                "@id": "images",
                "containedIn": {"@id": "images_dir"},
                "includes": "*.jpg",
                "encodingFormat": "image/jpeg",
            },
        ],
        "cr:recordSet": [
            {
                "@type": "cr:RecordSet",
                "@id": "#measurements",
                "name": "measurements",
                "description": "Measurement data from experiments",
                "cr:field": [
                    {
                        "@type": "cr:Field",
                        "@id": "#measurements/id",
                        "name": "id",
                        "description": "Measurement ID",
                        "dataType": "sc:Text",
                        "source": {
                            "fileObject": {"@id": "data_csv"},
                            "extract": {
                                "column": "id",
                            },
                        },
                    },
                    {
                        "@type": "cr:Field",
                        "@id": "#measurements/value",
                        "name": "value",
                        "description": "Measurement value",
                        "dataType": "sc:Float",
                        "source": {
                            "fileObject": {"@id": "data_csv"},
                            "extract": {
                                "column": "value",
                            },
                        },
                    },
                ],
            },
            {
                "@type": "cr:RecordSet",
                "@id": "#metadata",
                "name": "metadata",
                "description": "Metadata for measurements",
                "cr:field": [
                    {
                        "@type": "cr:Field",
                        "@id": "#metadata/id",
                        "name": "id",
                        "description": "Metadata ID",
                        "dataType": "sc:Text",
                        "source": {
                            "fileObject": {"@id": "metadata_json"},
                            "extract": {
                                "jsonPath": "$.id",
                            },
                        },
                    },
                ],
            },
        ],
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Configure the mock to return a successful validation result
    mock_process = mock.Mock()
    mock_process.stdout = "Validation successful"
    mock_process.stderr = ""
    mock_run.return_value = mock_process

    # Validate the complex metadata file
    validate_result = runner.invoke(validate, ["--jsonld", str(metadata_path)])

    # Check that validation was successful
    assert validate_result.exit_code == 0
    assert "Validation successful" in validate_result.output

    # Verify that subprocess.run was called with the correct arguments
    mock_run.assert_called_once_with(
        ["mlcroissant", "validate", "--jsonld", str(metadata_path)],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.mark.integration
def test_real_validation_with_mlcroissant_cli(runner, tmp_path):
    """Test that our metadata is actually valid using the real mlcroissant CLI."""
    # Create a metadata file using our tool
    output_path = tmp_path / "real_validation.json"

    # Run the create command with typical fields - using a name without special characters
    create_result = runner.invoke(
        create,
        [
            "--name",
            "RealValidationDataset",  # Changed to remove spaces
            "--description",
            "A dataset for testing real validation",
            "--data-source",
            "https://example.org/data",
            "--contact",
            "validator@example.org",
            "--date",
            "2023-10-15",
            "--access-restrictions",
            "Public",
            "--format",
            "CSV",
            "--output",
            str(output_path),
        ],
    )

    # Check that the file was created
    assert create_result.exit_code == 0
    assert os.path.exists(output_path)

    # Add recommended properties to the metadata
    with open(output_path) as f:
        metadata = json.load(f)

    # Add recommended properties
    metadata["license"] = "https://creativecommons.org/licenses/by/4.0/"
    metadata["version"] = "1.0"
    metadata["datePublished"] = "2023-10-15"
    metadata["citation"] = "Please cite this dataset as: RealValidationDataset (2023)"

    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Use mlcroissant CLI directly to validate the file
    try:
        result = subprocess.run(
            ["mlcroissant", "validate", "--jsonld", str(output_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        validation_successful = True
    except subprocess.CalledProcessError as e:
        validation_successful = False
        validation_error = e.stderr
        # Check if the error is just about warnings
        if "warning(s)" in e.stderr and "error(s)" not in e.stderr:
            validation_successful = True  # Consider warnings as acceptable

    # Check that validation was successful or skip if there are known compatibility issues
    assert validation_successful, (
        f"Validation failed with error: {validation_error if 'validation_error' in locals() else 'unknown error'}"
    )


def _write_simple_project_with_metadata(project_root: Path) -> Path:
    """Helper: create a minimal biotope project with one metadata file."""
    os.makedirs(project_root / ".git", exist_ok=True)
    datasets_dir = project_root / ".biotope" / "datasets" / "data"
    os.makedirs(datasets_dir, exist_ok=True)

    metadata_path = datasets_dir / "file1.jsonld"
    metadata = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "name": "data/file1.csv",
        "description": "Dataset for file1.csv",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "citation": "Please cite this dataset as: Example (2025)",
        "cr:projectName": "example-project",
        "distribution": [
            {
                "@type": "sc:FileObject",
                "@id": "file_abc12345",
                "name": "file1.csv",
                "contentUrl": "data/file1.csv",
            }
        ],
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata_path


def test_batch_to_csv_generates_project_csv(runner, tmp_path):
    """batch --to-csv creates .biotope.csv with rows from existing metadata."""
    project_root = tmp_path
    prev_cwd = os.getcwd()
    try:
        os.chdir(project_root)
        _write_simple_project_with_metadata(project_root)

        result = runner.invoke(annotate, ["batch", "--to-csv"])
        assert result.exit_code == 0

        csv_path = project_root / ".biotope.csv"
        assert csv_path.exists()

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        row = rows[0]
        # Required columns present and populated
        assert row["filepath"] == "data/file1.csv"
        assert row["description"] == "Dataset for file1.csv"
        # Optional columns exist in header
        assert "name" in row and "data_url" in row
    finally:
        os.chdir(prev_cwd)


def test_batch_from_csv_noop_when_unedited(runner, tmp_path):
    """batch --from-csv should not modify metadata when CSV is unedited."""
    project_root = tmp_path
    prev_cwd = os.getcwd()
    try:
        os.chdir(project_root)
        metadata_path = _write_simple_project_with_metadata(project_root)
        before = metadata_path.read_text(encoding="utf-8")

        # Generate CSV
        to_csv_result = runner.invoke(annotate, ["batch", "--to-csv"])
        assert to_csv_result.exit_code == 0
        csv_path = project_root / ".biotope.csv"
        assert csv_path.exists()

        # Import from CSV without changes
        from_csv_result = runner.invoke(annotate, ["batch", "--from-csv"])
        assert from_csv_result.exit_code == 0
        # The command cleans up the CSV file after applying
        assert not csv_path.exists()

        after = metadata_path.read_text(encoding="utf-8")
        assert before == after  # No change expected
        # Summary should report unchanged = 1
        assert "Unchanged: 1" in from_csv_result.output
    finally:
        os.chdir(prev_cwd)


def test_batch_from_csv_updates_when_edited(runner, tmp_path):
    """batch --from-csv should update metadata when CSV values change."""
    project_root = tmp_path
    prev_cwd = os.getcwd()
    try:
        os.chdir(project_root)
        metadata_path = _write_simple_project_with_metadata(project_root)

        # Generate CSV
        to_csv_result = runner.invoke(annotate, ["batch", "--to-csv"])
        assert to_csv_result.exit_code == 0
        csv_path = project_root / ".biotope.csv"
        assert csv_path.exists()

        # Edit CSV: change description and add encoding_format
        rows = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        assert rows
        rows[0]["description"] = "Updated description from CSV"
        rows[0]["encoding_format"] = "text/csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        # Apply from CSV
        from_csv_result = runner.invoke(annotate, ["batch", "--from-csv"])
        assert from_csv_result.exit_code == 0
        assert "Updated: 1" in from_csv_result.output

        # Verify metadata actually changed and distribution encodingFormat updated
        with open(metadata_path, encoding="utf-8") as f:
            updated = json.load(f)
        assert updated["description"] == "Updated description from CSV"
        # encodingFormat should be applied at top-level or on file objects per logic
        if "encodingFormat" in updated:
            assert updated["encodingFormat"] == "text/csv"
        if "distribution" in updated:
            for d in updated["distribution"]:
                if d.get("@type") == "sc:FileObject":
                    assert d.get("encodingFormat") == "text/csv"
    finally:
        os.chdir(prev_cwd)


def test_batch_from_csv_updates_creator_name(runner, tmp_path):
    """Changing the creator column in CSV should update creator.name in JSON-LD."""
    project_root = tmp_path
    prev_cwd = os.getcwd()
    try:
        os.chdir(project_root)
        metadata_path = _write_simple_project_with_metadata(project_root)
        with open(metadata_path, encoding="utf-8") as f:
            original = json.load(f)
        # Ensure creator exists initially (or add minimal one)
        if "creator" not in original:
            original["creator"] = {"@type": "Person", "name": "Old Name"}
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(original, f, indent=2)

        # Generate CSV
        to_csv_result = runner.invoke(annotate, ["batch", "--to-csv"])
        assert to_csv_result.exit_code == 0
        csv_path = project_root / ".biotope.csv"
        assert csv_path.exists()

        # Edit CSV: change creator
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        assert rows
        rows[0]["creator"] = "New Creator Name"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        # Apply from CSV
        from_csv_result = runner.invoke(annotate, ["batch", "--from-csv"])
        assert from_csv_result.exit_code == 0
        assert "Updated:" in from_csv_result.output

        # Verify creator updated
        with open(metadata_path, encoding="utf-8") as f:
            updated = json.load(f)
        assert updated.get("creator", {}).get("name") == "New Creator Name"
    finally:
        os.chdir(prev_cwd)

@pytest.mark.integration
def test_real_validation_complex_metadata_cli(runner, tmp_path):
    """Test that complex metadata is actually valid using the real mlcroissant CLI."""
    # Create a complex metadata file directly
    metadata_path = tmp_path / "real_complex_metadata.json"

    # Create a more complex metadata structure with file objects and record sets
    # Use the standard Croissant context to ensure compatibility with mlcroissant validator
    from biotope.commands.annotate import get_standard_context
    metadata = {
        "@context": get_standard_context(),
        "@type": "Dataset",
        "name": "RealComplexTestDataset",  # Removed spaces
        "description": "A dataset with multiple file objects and record sets for real validation",
        "url": "https://example.org/complex-data",
        "creator": {
            "@type": "Person",
            "name": "complex@example.org",
        },
        "dateCreated": "2023-09-01",
        "datePublished": "2023-09-01",  # Added recommended property
        "version": "1.0",  # Added recommended property
        "license": "https://creativecommons.org/licenses/by/4.0/",  # Added recommended property
        "citation": "Please cite this dataset as: RealComplexTestDataset (2023)",  # Added recommended property
        "cr:accessRestrictions": "Academic use only",
        "encodingFormat": "Mixed",
        "distribution": [
            {
                "@type": "sc:FileObject",  # Changed from cr:FileObject to sc:FileObject
                "@id": "data_csv",
                "name": "data.csv",
                "contentUrl": "https://example.org/complex-data/data.csv",
                "encodingFormat": "text/csv",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # Added SHA256
            },
            {
                "@type": "sc:FileObject",  # Changed from cr:FileObject to sc:FileObject
                "@id": "metadata_json",
                "name": "metadata.json",
                "contentUrl": "https://example.org/complex-data/metadata.json",
                "encodingFormat": "application/json",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # Added SHA256
            },
        ],
        "cr:recordSet": [
            {
                "@type": "cr:RecordSet",
                "@id": "#measurements",
                "name": "measurements",
                "description": "Measurement data from experiments",
                "cr:field": [
                    {
                        "@type": "cr:Field",
                        "@id": "#measurements/id",
                        "name": "id",
                        "description": "Measurement ID",
                        "dataType": "sc:Text",
                        "source": {
                            "fileObject": {"@id": "data_csv"},
                            "extract": {
                                "column": "id",
                            },
                        },
                    },
                ],
            },
        ],
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Use mlcroissant CLI directly to validate the file
    try:
        result = subprocess.run(
            ["mlcroissant", "validate", "--jsonld", str(metadata_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        validation_successful = True
    except subprocess.CalledProcessError as e:
        validation_successful = False
        validation_error = e.stderr
        # Check if the error is just about warnings
        if "warning(s)" in e.stderr and "error(s)" not in e.stderr:
            validation_successful = True  # Consider warnings as acceptable

    # Check that validation was successful or skip if there are known compatibility issues
    assert validation_successful, (
        f"Validation failed with error: {validation_error if 'validation_error' in locals() else 'unknown error'}"
    )
