# How biotope works

Biotope has two jobs:

1. Track datasets and their Croissant metadata with git-like commands.
2. Turn Croissant-described data into a runnable BioCypher project.

The installed `biotope` package does not import BioCypher or BioChatter. A
generated project declares BioCypher as its graph writer; BioChatter can query
the loaded graph later.

## Project layout

```text
my-kg/
├── .biotope/
│   ├── project.yaml       graph purpose and required entities or relations
│   ├── config.yaml        validation and registry settings
│   ├── datasets/          Croissant metadata for tracked data
│   └── workflows/         reserved
├── data/                  tracked data; ignored by Git
├── mappings/              semantic mappings
├── alignment.yaml         optional cross-dataset equivalences
├── build/                 generated BioCypher project
├── pyproject.toml         project dependencies
└── .gitignore
```

`biotope init --visible` writes `project.yaml` at the project root. Other
managed files remain under `.biotope/`. Commands find the nearest project by
walking upward from the current directory.

Dataset state (`raw`, `processed`, or `mapped`) lives in each Croissant
manifest, not in the `data/` directory structure.

## Data flow

```text
biotope init
    │
    ├─ biotope map --purpose/--entity/--relation
    │      └─ .biotope/project.yaml
    │
data files
    └─ biotope add
           └─ .biotope/datasets/*.jsonld
                    │
                    └─ biotope map inspect/scaffold/preview
                           └─ mappings/*.mapping.yaml
                                    │
                                    ├─ biotope propose-alignment (optional)
                                    │      └─ alignment.yaml
                                    │
                                    └─ biotope build
                                           └─ build/
                                                ├─ config/schema_config.yaml
                                                ├─ generated/*/adapter.py
                                                └─ create_knowledge_graph.py
```

`biotope add` uses
[croissant-baker](https://github.com/biocypher/croissant-baker) to infer
structural metadata where possible. Mapping connects Croissant record sets and
fields to graph entities and relations. `build` compiles resolved mappings into
BioCypher tuple streams.

## Semantic decisions and determinism

Biotope catalogs fields, validates mappings, and previews tuples. A human or
agent chooses record sets, identifiers, transforms, entities, and relations.
`build` rejects unresolved mapping slots and the removed `nodes`/`edges`
mapping schema.

With the same Croissant manifests, mappings, alignment, and data, compilation
produces the same generated project. LLMs sit above this deterministic
boundary:

```text
human or agent → biotope CLI → biotope.croissant.api → generated project
```

## Configuration

| File | Purpose |
| --- | --- |
| `.biotope/project.yaml` | Graph purpose, entities, relations, and data sources |
| `.biotope/config.yaml` | Croissant version, validation rules, and registry URLs |
| `.biotope/datasets/*.jsonld` | Generated and curated Croissant metadata |
| `mappings/*.mapping.yaml` | Authored entity and relation mappings |
| `alignment.yaml` | Optional `same_node` equivalences across mappings |

Settings resolve from lowest to highest priority:

```text
~/.config/biotope/config.yaml
→ .biotope/config.yaml
→ .biotope/project.yaml
→ CLI flags
```

Inspect resolved project intent with `biotope map --show`.

## Agent interface

Plugin skills are the default agent contract:

```text
biotope-croissant → biocypher → biochatter
```

Each skill covers one pipeline stage and invokes public CLI commands.
`biotope init --agents-md` can add a root `AGENTS.md` for agents without skill
support. See [Plugin and skills](plugin.md) for setup.

For Python integrations, `biotope.croissant.api` exposes the deterministic
functions used by the CLI.
