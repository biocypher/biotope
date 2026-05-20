# Biotope Annotate

!!! warning "Draft stage"

    Biotope is in draft stage. Functionality may be missing or incomplete.
    The API is subject to change.

`biotope annotate` is the editorial companion to `biotope add`.

- `biotope add` creates or refreshes the canonical JSON-LD.
- `biotope annotate apply` merges bulk human edits from a scoped CSV.
- `biotope annotate edit` is the interactive fallback.
- `biotope status` remains the completeness gate.

## Commands

### `biotope annotate apply`

Apply a scoped `.biotope.csv` scaffold to one dataset JSON-LD.

**Usage**

```bash
biotope annotate apply <dir-or-csv> [--set KEY=VALUE ...]
```

`<dir-or-csv>` can be:

- a dataset directory, which resolves to `<dir>/.biotope.csv`
- a CSV file, typically the scaffold produced by `biotope add <dir>`

`--set` applies row-wide overrides at apply time. Bare keys default to the
dataset scope for shared fields. Use `dataset.<field>=...` or
`record_set.<field>=...` for explicit scope.

**Examples**

```bash
# Apply the scaffold next to a dataset directory
biotope annotate apply data/raw/opentargets

# Apply an explicit CSV file
biotope annotate apply data/raw/opentargets/.biotope.csv

# Override one dataset field at apply time
biotope annotate apply data/raw/opentargets --set creator="Open Targets Consortium"

# Override a record-set field across all record-set rows
biotope annotate apply data/raw/opentargets --set record_set.description="Needs review"
```

### Scoped CSV format

`biotope add <dir>` writes one `.biotope.csv` scaffold per dataset directory.
The CSV has one dataset row and zero or more record-set rows:

```csv
scope,record_set_id,source_path,name,description,creator,creator_email,license,url,citation,version,keywords,access_restrictions,legal_obligations,collaboration_partner,encoding_format
dataset,,data/raw/opentargets,Open Targets,OT v3,Open Targets,info@opentargets.org,CC-BY-4.0,https://opentargets.org,Please cite...,3,gene;disease;variant,public,,,
record_set,#genes,data/raw/opentargets/genes,genes,Gene table,,,,,,,,,,,application/parquet
record_set,#diseases,data/raw/opentargets/diseases,diseases,Disease table,,,,,,,,,,,application/parquet
```

Join rules:

- exactly one `scope=dataset` row is required
- `scope=record_set` rows join on `record_set_id`
- `source_path` is for human context, not as a primary key

### `biotope annotate edit`

Interactive metadata editing for one file or tracked file set.

**Usage**

```bash
biotope annotate edit [OPTIONS]
```

**Options**

- `--file-path, -f`: specific file to annotate
- `--prefill-metadata, -p`: JSON string with pre-filled metadata
- `--staged, -s`: annotate staged files
- `--incomplete, -i`: revisit tracked files with incomplete metadata

**Examples**

```bash
biotope annotate edit --staged
biotope annotate edit --incomplete
biotope annotate edit --file-path data/raw/experiment.csv
```

`biotope annotate interactive` remains available as a hidden alias.

### `biotope annotate validate`

Validate a Croissant metadata file using the `mlcroissant` CLI.

```bash
biotope annotate validate --jsonld .biotope/datasets/data/opentargets.jsonld
```

### `biotope annotate load`

Load records from a dataset using its Croissant metadata.

```bash
biotope annotate load --jsonld .biotope/datasets/data/opentargets.jsonld --record-set genes
```

## Completeness

Use `biotope status` to see whether tracked metadata meets the current
annotation requirements.

::: biotope.commands.annotate
