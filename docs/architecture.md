# How Biotope works

Croissant-baker parses source formats and assembles structural metadata. Biotope
tracks that metadata, captures research intent, and checks mapping definitions.
It does not implement source readers or execute mappings in the supported
workflow. Project-specific loading and transformation are later work.

## Project layout

```text
project/
├── .biotope/
│   ├── project.yaml       purpose and required entities/relations
│   ├── config.yaml        metadata validation settings
│   ├── datasets/          tracked Croissant metadata
│   └── workflows/         reserved
├── data/                  conventional local data directory
├── mappings/              authored mapping YAML
├── alignment.yaml         optional mapping equivalence suggestions
├── pyproject.toml
└── .gitignore
```

`init --visible` puts `project.yaml` at the root. Other managed files stay under
`.biotope/`. Tracking commands locate a project by walking upward to `.biotope/`
and `.git/`. Data paths must stay within the project.

## Data flow

```text
local files → add (baker) → Croissant manifests → inspect/scaffold
                                                     ↓
map --purpose/--entity/--relation → project.yaml → mapping YAML → preview
```

Directory and single-file ingestion use baker's assembly. A file can describe
multiple record sets. Distinct IDs preserve identities when display names
collide. Unsupported files can be tracked without invented field descriptions.

Inspection, scaffolding, the wizard and structural checks use manifests and
mapping definitions. They work without source payloads. File tracking may read
checksums or timestamps; it does not inspect data values.

Purpose and entity/relation lists stay in project metadata. Detailed schema and
selector choices stay in mapping YAML. This iteration preserves that model.

## Configuration

Settings resolve from lowest to highest priority:

```text
~/.config/biotope/config.yaml → .biotope/config.yaml → project.yaml → CLI flags
```

Inspect intent with `biotope map --show`. Dataset state lives in each manifest:
`raw`, `processed` or `mapped`. State and passing structural checks do not prove
value validity, transform correctness or graph readiness.

## Agent interface

The `biotope-croissant` skill guides agents through the same CLI workflow.
`init --agents-md` optionally writes project guidance for other agents. See
[Plugin and skills](plugin.md). Python integrations can use the metadata and
mapping functions in `biotope.croissant.api`.

Downstream graph modules remain in the repository but are unsupported and
detached from CLI registration. They are not part of this integration's tests.
