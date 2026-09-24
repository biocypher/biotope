# Migrating to Biotope 0.10

Biotope 0.10 makes the shape of a graph project explicit. Every described input is
inventoried and either selected or excluded with a reason; source schemas are
scaffolded once and then authored; a changed description is reported as drift;
and interpretation travels in descriptions, policies and scope instead of a query
context. Project validation callbacks are retired.

## What 0.10 no longer does

These are deliberate reductions. Plan for them before upgrading.

1. **No automated scientific verification.** Project validation checks and
   per-capability states are gone, and the remaining generic checks are not
   equivalent: they cannot see a record that should have been emitted but was not.
   Review claims at hand-over against expectations read independently from the
   sources or published results.
1. **No interpretation inside the graph.** `BiotopeQueryContext` rows,
   `query_context.json` and runnable query examples are gone. Interpretation now
   lives in the concept and property descriptions in `schema_config.yaml` and in
   `run.json`'s policies and scope. A consumer with only the database sees labels,
   properties and `biotope_provenance_id`, so `graph/build/` must travel with the
   graph.
1. **Indirect evidence.** Provenance is reached through `biotope_provenance_id` in
   `provenance.json` instead of an inline `provenance.jsonl`.
1. **One current build.** `biotope graph build` replaces `graph/build/` after a
   successful run instead of creating a new run directory; `--out` still chooses
   another location.
1. **Printed quality.** `biotope graph quality` prints its results instead of
   writing `graph/reports/quality.json`. A build records quality in `run.json`.
1. **Schemas are never re-rendered.** Generated schemas, 0.9 ones included, no
   longer follow description changes: every contract change surfaces as
   `source.drift` for review. Authored types are not compared with Croissant
   `dataType` or nullability.
1. **Scoped field `@id`s.** New scaffolds bind fields through `@id`s scoped under
   their record set, as croissant-baker and `biotope annotate` write them. Other
   ids produce `source.unscoped_field`; an existing `__field_refs__` mapping still
   binds them.
1. **Package names depend on history.** A new package's name is deterministic given
   the manifest and the directories that already exist, so it can differ from a
   from-scratch generation.

## Removed and changed APIs

| Removed or changed                                                                                                       | Replacement                                                                                                              |
| ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `QueryContext`, `Capability`, `Interpretation`, `QueryExample`, `Pipeline(query_context=)`                               | Concept and property descriptions; `Pipeline.policies` and `scope`; `graph/ASSUMPTIONS.md` for open scientific questions |
| `ValidationCheck`, `ValidationResult`, `GraphView`, `RunContext.view()` and `snapshot()`, `Pipeline(validation_checks=)` | CLI and runtime checks; review-time independent reads                                                                    |
| `SourceContract(generated=)`                                                                                             | `schema=`                                                                                                                |
| `topology.json`, `ontology.ttl`, `provenance.jsonl`, the required `build --out`                                          | `schema_config.yaml`, headless export, `provenance.json`, the `graph/build/` default                                     |
| `graph/reports/{quality.json,metagraph.html}`                                                                            | printed quality; `graph/metagraph.html`                                                                                  |
| `biotope init --agents-md`, `templates/AGENTS.md`                                                                        | the plugin skills                                                                                                        |
| report `schema_version: 1`                                                                                               | `2`; replacement and `--report` accept both 1 and 2                                                                      |

Removed keywords fail with ordinary unknown-keyword `TypeError`s. Export labels now
use a concept's local name (`Gene` rather than `CvdGene`), widened only when two
concepts collide.

## Migrate a 0.9 project

1. Delete `graph/checks.py` and `graph/query_context.py`, and remove their
   `Pipeline` arguments (`validation_checks=`, `query_context=`) and `code_paths`
   entries.
1. Replace `generated=` with `schema=` in each source registration.
   `records=RECORDS` and `SourceRow` keep working.
1. Wire the inventory: in `graph/sources/__init__.py`, import `INVENTORY` from
   `.inventory`, declare `EXCLUDED_SOURCES: dict[str, str]` and select
   `SOURCES = tuple(s for s in INVENTORY if s.name not in EXCLUDED_SOURCES)`; pass
   `source_inventory=INVENTORY` and `excluded_sources=EXCLUDED_SOURCES` to the
   `Pipeline`.
1. Move old `graph/build/<run>/` directories out of the way.
1. Delete `graph/reports/`.
1. Move drafts in `graph/metadata/` to `.biotope/reviews/`.
1. Run `biotope source generate <manifest> --out graph/sources` once per manifest.
   It adopts the existing packages, rewrites each 0.9 root into the collecting
   form, creates `graph/sources/inventory.py` and packages for inputs that had
   none, and records every revision in `.biotope/contracts/`.

Then run `biotope graph check` and resolve its findings: select or exclude every
inventoried source, implement or exclude placeholder loaders, and describe
concepts and properties that `topology.undescribed*` names.

## Earlier: migrating to Biotope 0.9

Biotope 0.9 replaced the YAML mapping engine with typed Python graph projects.
Metadata tracking, annotation commands and purpose capture remain available.

### Graph projects

| Earlier workflow                                  | Biotope 0.9                                                 |
| ------------------------------------------------- | ----------------------------------------------------------- |
| YAML mapping files and interactive mapping wizard | Python topology, loaders, mappings and an explicit pipeline |
| `biotope map scaffold` and `biotope map preview`  | `biotope graph scaffold`, then `biotope graph check`        |
| `biotope build`                                   | `biotope graph build`                                       |
| Mapping and alignment proposals                   | Project-owned choices recorded in Python and metadata       |

There is no automatic conversion of existing mappings. Keep them as a reference,
review the intended identities and transformations, and implement a Python
workspace using the [typed graph guide](mapping.md). The [tutorial](tutorial.md)
shows a complete project.

Install `biotope[graph]` for graph checking and export. The published package
resolves croissant-baker from PyPI; remove development-only sibling-directory
overrides from your own environment when moving to the public release.

### Sources and commands

`biotope add` describes local sources through croissant-baker. Review and curate
those descriptions before generating source packages. Each top-level record set
gets its own Python source package; project loaders implement physical access.

The earlier `discover`, `search`, `get`, `read`, `view`, `benchmark`,
`propose-mapping` and `propose-alignment` commands have been removed.
Use external tools for discovery or download and established format libraries
inside your project loaders.

`biotope map --purpose`, `--entity` and `--relation` retain research requirements.
Bind those requirements to topology concepts or record explicit deferrals in the
pipeline. They do not define an executable mapping by themselves.

See [commands](commands.md) for the current CLI and use `biotope --help` to check
the commands available in your installed version.
