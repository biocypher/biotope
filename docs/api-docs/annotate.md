# Biotope Annotate

!!! warning "Draft stage"

    Biotope is in draft stage. Functionality may be missing or incomplete.
    The API is subject to change.

`biotope annotate` is the editorial companion to `biotope add`.

- `biotope add` creates or refreshes the canonical JSON-LD.
- `biotope annotate apply` merges bulk human edits from a scoped YAML scaffold.
- `biotope annotate edit` is the interactive fallback.
- `biotope status` remains the completeness gate.

## Commands

### `biotope annotate apply`

Apply a scoped `.biotope.yaml` scaffold to one dataset JSON-LD.

**Usage**

```bash
biotope annotate apply <dir-or-yaml> [--set KEY=VALUE ...]
```

`<dir-or-yaml>` can be:

- a dataset directory, which resolves to `<dir>/.biotope.yaml`
- a YAML file (`.biotope.yaml` or another scaffold path), typically the one produced by `biotope add <dir>`

`--set` applies overrides at apply time. Bare keys default to the
dataset scope for shared fields. Use `dataset.<field>=...` or
`record_set.<field>=...` for explicit scope.

**Examples**

```bash
# Apply the scaffold next to a dataset directory
biotope annotate apply data/raw/opentargets

# Apply an explicit scaffold file
biotope annotate apply data/raw/opentargets/.biotope.yaml

# Override one dataset field at apply time
biotope annotate apply data/raw/opentargets --set creator="Open Targets Consortium"

# Override a record-set field across all record-set rows
biotope annotate apply data/raw/opentargets --set record_set.description="Needs review"
```

### Scaffold format

`biotope add <dir>` writes one `.biotope.yaml` per dataset directory. The
scaffold has one `dataset` block and a `record_sets` list:

```yaml
dataset:
  source_path: data/raw/opentargets
  name: Open Targets
  description: OT v3
  creator: Open Targets
  creator_email: info@opentargets.org
  license: CC-BY-4.0
  url: https://opentargets.org
  citation: "Please cite..."
  version: "3"
  keywords: [gene, disease, variant]
  access_restrictions: public

record_sets:
  - id: "#genes"
    source_path: data/raw/opentargets/genes
    name: genes
    description: Gene table
    encoding_format: application/parquet
  - id: "#diseases"
    source_path: data/raw/opentargets/diseases
    name: diseases
    description: Disease table
    encoding_format: application/parquet
```

Join rules:

- exactly one `dataset` block is required
- each `record_sets[]` entry joins to a `recordSet[]` in the JSON-LD by `id`
- unknown `id`s and missing `dataset` blocks are hard errors
- `source_path` is for human context, not a primary key

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
