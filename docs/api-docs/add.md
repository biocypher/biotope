# Biotope Add

!!! warning "Draft stage"

```
Biotope is in draft stage. Functionality may be missing or incomplete.
The API is subject to change.
```

`biotope add` is the structural entrypoint for tracking data in a biotope
project.

- `biotope add <file>` creates one JSON-LD for that file.
- `biotope add <dir>` recurses by default and creates one JSON-LD for the
  rooted tree.
- Parseable files get croissant-baker structure.
- Unhandled files are still tracked as `cr:FileObject` pointers.

## Command Signature

```bash
biotope add [OPTIONS] [PATHS]...
```

## Options

- `--force, -f`: force add even if a file is already tracked
- `--name`: dataset name override
- `--description`: dataset description override
- `--license`: dataset license
- `--creator`: dataset creator name
- `--creator-email`: dataset creator email
- `--url`: dataset URL
- `--citation`: dataset citation text
- `--version`: dataset version
- `--keyword`: dataset keyword, repeatable
- `--access-restrictions`: dataset access restrictions
- `--legal-obligations`: dataset legal obligations
- `--collaboration-partner`: dataset collaboration partner
- `--rai KEY=VALUE`: Croissant RAI field, repeatable

## Examples

### Add a single file

```bash
biotope add data/experiment.csv --license CC-BY-4.0
```

### Add a directory

```bash
biotope add data/opentargets \
  --license CC-BY-4.0 \
  --creator "Open Targets" \
  --description "Open Targets release"
```

### Force re-add a tracked file

```bash
biotope add data/experiment.csv --force
```

## What It Does

1. Validates that you are inside a biotope project and Git repository.
1. Creates or refreshes metadata in `.biotope/datasets/`.
1. Uses croissant-baker for parseable files.
1. Appends `cr:FileObject` pointers for unparseable files in directory adds.
1. Stages `.biotope/` changes in Git.

When you add a directory, biotope also writes `<dir>/.biotope.yaml` so the
dataset can be refined collaboratively with `biotope annotate apply`.

## Raw and Processed Datasets

`raw` and `processed` are pipeline states, not quality labels. A curated
resource can still enter the queue as `raw` if biotope cannot see a concrete
record schema for mapping.

`biotope add` assigns the initial state from the Croissant metadata produced by
croissant-baker:

- `processed`: the manifest has at least one `recordSet` with fields. The
  dataset is schema-shaped and ready for `biotope map`.
- `raw`: the manifest has no mappable `recordSet` fields. The file is still
  tracked for provenance, but it needs extraction, conversion, annotation, or a
  manual correction before it can be mapped.

For example, a well-curated Open Targets table will normally be `processed`
when croissant-baker can infer the columns and field types. A PDF, free-text
notes file, opaque archive, or URL-only resource will normally stay `raw` until
a human or agent creates a structured derivative.

When you derive a structured file from a raw input, keep the provenance link:

```bash
biotope add data/derived-table.csv --derived-from data/source-notes.md
```

If the automatic state is wrong, correct it explicitly instead of moving files
between directories:

```bash
biotope mark data/derived-table processed
```

## Follow-on workflow

```bash
biotope add data/opentargets --license CC-BY-4.0 --creator "Open Targets"
biotope annotate apply data/opentargets
biotope status
biotope commit -m "Track Open Targets dataset"
```

## Output shape

Single-file adds always emit a `cr:FileObject`. When baker can infer structure,
the same JSON-LD may also contain `recordSet` entries.

Directory adds emit one aggregate JSON-LD:

- `cr:FileSet` and `recordSet` entries for handled formats
- `cr:FileObject` entries for uncovered files

::: biotope.commands.add
