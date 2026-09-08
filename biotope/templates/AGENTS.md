# Agent instructions for this Biotope project

Use the Biotope CLI to describe local data, capture research purpose and target
schema, and author mappings. The supported workflow stops at structural mapping
checks. Loading, transformations and graph construction belong to later
project-specific work.

Use the installed environment. During local integration, install both Biotope
and the merged croissant-baker checkouts into that environment. Do not switch to
an older published package with `uvx`.

## Workflow

1. Read existing intent with `biotope map --show`. Establish the research
   question, entities and relations from the user's instructions. Ask about
   missing or conflicting choices. Do not silently clear or replace intent.
1. Select explicit local data paths inside the project. Run `biotope add <path>`
   to describe them through baker. Start small for large datasets; checksums read
   bytes. Exclude environments, skills, logs and earlier outputs from scans.
1. Review progress, coverage and per-file diagnostics. Some inputs may be
   partially described, unsupported or malformed. Do not invent missing fields
   or extract text to fill these gaps.
1. Use `biotope map inspect <manifest> --json` and
   `biotope map scaffold <manifest>`. Edit the resulting `mappings/*.mapping.yaml`
   against declared fields. Select record sets by ID when names collide.
1. Run `biotope map preview --json`. Review unresolved slots, findings and the
   proposed schema. Report checked scope, artifacts and limitations, then stop.

Intent flags are non-interactive:

```bash
biotope map --purpose "The agreed question" --entity gene --relation gene_in_pathway
```

Bare `biotope map` opens the human wizard. `map --help` and subcommand help
explain the available options. The `biotope-croissant` skill contains mapping
syntax and further guidance.

## Metadata and state

Managed manifests live under `.biotope/datasets/`; purpose and required schema
slots live in project metadata. Use CLI commands for managed files; author YAML
only in `mappings/`. A single file may describe several record sets. Regenerate changed
directories with `biotope add <directory> --rebake` or individual files with
`biotope add <file> --force`, then review their mappings.

`queue` reports coarse states: `raw` has no field description, `processed` has
described fields, and `mapped` has a mapping marked defined. None establishes
valid source values or a working graph. Passing structural checks does not
validate identifiers, joins, transformations or scientific correctness. Empty
stubs are inactive in this model: compare resolved slots with project intent
even when checks pass.

Use `annotate` and `config` for metadata curation; `check-data` for checksums;
`mv` and `rm` for tracked paths; `status`, `commit` and `log` for metadata history.
Do not edit raw payloads or implement loaders during this workflow. Keep the
user's schema intact when data cannot support it: record the gap and discuss
whether to defer a relation or change the schema.
