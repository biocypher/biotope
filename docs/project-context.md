# Project context

A *biotope project* is a directory containing scientific data, its Croissant metadata, and the configuration that drives builds. Every command operates on the nearest enclosing project, found by walking upward to a `.biotope/` directory (or a visible `project.yaml`).

## Layout

```
my-kg/
├── .biotope/
│   ├── project.yaml        competence questions (purpose, required_entities, …)
│   ├── config.yaml         technical settings (validation, registries)
│   ├── datasets/           one Croissant .jsonld per tracked file
│   └── workflows/          (reserved)
├── data/{raw,processed}/   actual data; gitignored by default
├── mappings/               *.mapping.yaml — declarative KG mappings
├── alignment.yaml          (optional) cross-Croissant alignment
├── build/                  output of `biotope build`
├── AGENTS.md               agent instructions
└── .gitignore
```

`--visible` at `init` time promotes `project.yaml` and `config.yaml` from `.biotope/` to the project root for users who don't want a dotfolder.

## `.biotope/project.yaml`

The competence-questions document — the only place where content-level intent lives.

```yaml
name: my-kg
purpose: What approved drugs target genes implicated in T2D?
required_entities: [gene, disease, drug]
required_relations: [gene_associated_with_disease, drug_targets_gene]
data_sources: []
notes: ""
```

Populated by:

- `biotope init --purpose "..."` (one-shot)
- `biotope map --entity ... --relation ... --purpose "..."` (incremental, non-interactive)
- The agent reading `AGENTS.md` (which in turn calls `biotope map` with intent flags)

Read by:

- `biotope discover` — ranks adapters/files by overlap with `required_entities`.
- `biotope build` — informs `schema_config.yaml` generation.

## Configuration precedence

```
CLI flag                              ← highest
  ↑
.biotope/project.yaml                 (or ./project.yaml if --visible)
  ↑
.biotope/config.yaml
  ↑
~/.config/biotope/config.yaml         ← lowest
```

CLI flags always win. Inspect resolved values with `biotope map --show`.

## `.biotope/datasets/<name>.jsonld`

One Croissant 1.1 JSON-LD file per tracked data file. `biotope add` writes the file-level stub; if `croissant-baker` has a handler for the file's extension, structural metadata (column types, row counts) is appended automatically. Fields baker cannot infer (license, creator, access restrictions) come from CLI flags on `biotope add`.

These files are the input to `biotope map scaffold` (which produces an
unresolved semantic mapping) and to `biotope build` (which compiles it).

## Why this shape

- The dotfolder keeps tool-managed files out of the user's way without coupling to git.
- One canonical place for content intent (`project.yaml`) avoids the "where do the competence questions live" question.
- Hierarchical config matches BioCypher's pattern and lets shared registry URLs live in `~/.config/biotope/config.yaml`.
- Everything except `project.yaml` and `mapping.yaml` overrides can be regenerated, which keeps the project portable.
