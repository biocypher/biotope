---
name: biotope-croissant
description: Builds typed knowledge-graph projects with Biotope from local data described in Croissant. Covers registering and curating manifests for tables and documents, generating the complete source inventory, authoring source schemas, loaders, shared terms, identity alignment, topology with descriptions, mappings and the pipeline, then checking and exporting through BioCypher. Use whenever the user works in a project with a `.biotope/` directory or a `graph/` workspace, runs or asks about `biotope add`, `biotope source generate`, `biotope graph check` or `biotope graph build`, wants to turn CSV, Excel, Parquet or other data files and papers into a knowledge graph, needs to resolve inventory or `source.drift` findings after a metadata change, or migrates a Biotope 0.9 project, even if they do not name Biotope or Croissant.
---

# Biotope graph projects

**Terms used throughout.**

- **Manifest**: a registered Croissant description, `.biotope/datasets/<name>.jsonld`. Drafts live in `.biotope/reviews/`.
- **Source**: one input the graph may read — a RecordSet, or a file no RecordSet reads (a paper, notes, an image). Each source has a **package**, `graph/sources/<manifest>/<source>/`, holding its schema, `SOURCE` registration and loader.
- **Revision**: a digest of one source's contract in the manifest. A schema's `__source_digest__` records the revision you reviewed.

**What you deliver.** `graph/build/`: BioCypher import files, `schema_config.yaml` with every concept and property description, `provenance.json`, and `run.json` with the scope, policies, bindings, counts and exclusions. The consumer gets the graph and `graph/build/`, never this repository or your reasoning, so everything needed to read a value correctly belongs in a description, a policy or the scope.

**Ownership.** The user owns scientific decisions; you own engineering ones. Reuse decisions already made. Ask about missing ones that change selection or identity; when no one can answer, apply the default this skill names and record the question in `graph/ASSUMPTIONS.md` and the hand-over. Never settle a scientific question silently.

**Scope.** Curation, scaffolding and execution are independent: do the steps the request needs. Describing a dataset does not imply building a graph. Database import, querying and new Baker format handlers are separate work.

## Workflow

Copy this checklist and track progress.

```
Biotope graph project:
- [ ] Step 1: Read the inputs and the existing project
- [ ] Step 2: Agree the purpose and requirements
- [ ] Step 3: Describe and register every source
- [ ] Step 4: Generate the inventory and decide exclusions
- [ ] Step 5: Author schemas and terms, then loaders
- [ ] Step 6: Declare the topology by concept
- [ ] Step 7: Align identities, then write mappings and the pipeline
- [ ] Step 8: Check, fix, build
- [ ] Step 9: Review and hand over
```

**Step 1: Read the inputs and the existing project.**

- Run every command from the project root. Read purpose files, `biotope map --show`, and `graph/README.md` if a workspace exists; it documents the layout you will edit.
- Graph checks and builds need `biotope[graph]`; Pyright needs Node.js on `PATH` or `pyright[nodejs]`.
- Create only what is missing: `biotope init . --no-prompt` for metadata tracking, `biotope graph scaffold` for the workspace.
- Write no project code yet.

**Step 2: Agree the purpose and requirements.**

- A purpose and its example questions are evidence of intent, not a specification. Derive the adjacent questions: the neighbouring comparison, evidence that would contradict the expected answer, a second defensible reading of the same statistic, the context needed to interpret a result, and the case where a well-founded "no such record" is the answer. For each, name the evidence and distinctions it needs: that list decides what the sources must supply and what the mappings must admit.
- Record the agreed purpose with `biotope map --purpose "..." --entity "..." --relation "..."`. Propose adjacent requirements once, with their cost; record declined ones as out of scope.

**Step 3: Describe and register every source.**

- Describe new inputs with `biotope add <data-path> --json` and review each file's outcome. Do not scan environments or previous outputs. Keep the requested scope, including whole directories; never split a Croissant file to shape the packages, and never invent structure to make a mapping work.
- `biotope add` also writes an annotation template, `<data-path>/.biotope.yaml`, and pre-fills the manifest's `creator` from the local git identity and its `license` with Baker's default, CC BY 4.0. Neither describes the data. The creator is whoever produced the data, which the person running the tools usually is not. In your first correction, keep a creator or licence only where the data's documentation or the user explicitly states it for this data; otherwise remove it and record the question. Do not fill it with any identity from the environment, such as the git user or the account you work for.
- Files Baker cannot parse are reported `unclaimed`, and `biotope add` still gives each a FileObject whose `@id` follows its checksum. Keep these. A document, such as a paper or notes, becomes a document source whose package holds the facts you transcribe. A structured file the graph reads records from, such as tab-separated `.txt`, RDF or a shapefile, needs a RecordSet over that FileObject instead. Add a FileObject by hand only for a file outside the scanned paths. Both are in [curation.md](./references/curation.md).
- Inspect fields and exact IDs with `biotope map inspect <manifest> --json`, which reads metadata only.
- To correct a manifest, copy it into `.biotope/reviews/`, edit the copy, and register it: `biotope source register <draft> --name <name> --reason "<evidence and gaps>" --replace`. Never edit `.biotope/datasets/` directly.
- A metadata-only request ends here.

**Step 4: Generate the inventory and decide exclusions.**

- Run `biotope source generate .biotope/datasets/<name>.jsonld --out graph/sources` once per manifest. Every source gets a package with a schema, a `SOURCE` registration and a placeholder loader. Existing files are never rewritten, and every revision is recorded in `.biotope/contracts/`.
- In `graph/sources/__init__.py`, each source is either selected or listed in `EXCLUDED_SOURCES` with a reason a reviewer can check. To leave a source out, exclude it. Deleting its package does not remove it: the next generation recreates the package and the check reports it as stale.

**Step 5: Author schemas and terms, then loaders.** Before writing the first schema, loader or mapping, read [example.md](./references/example.md): a complete small project that passes the check, file by file. The references document the contracts you build against; the installed package's source is internal and changes between releases.

- A generated `schema.py` is yours: rename attributes, tighten types, set `__missing_values__`, and bind each Croissant field exactly once with `source_field(...)`. The check enforces complete coverage, so no described field is silently dropped. Examples are in [authoring.md](./references/authoring.md).
- Encodings are local to their source: missing-value tokens, value aliases and species context go in that schema. They are declarations only; the loader applies them.
- Whenever the graph will read fields of several sources as one meaning, such as a fold change or an adjusted p-value that one property collects from several tables, declare that meaning once as a `Term` in `standardization.py`, and bind each of those fields to it with `source_field(..., term=...)` on an attribute named after the term. The check validates the bindings, and `run.json` shows reviewers which source fields were treated as equivalent. An equivalence written only into mapping code is invisible to them. Bind a field only after reading what each source means by it, since matching names establish no equivalence. A field kept as its source reported it needs no term.
- Generated directory and class names follow the manifest's ids and can be long. Both are yours: a package belongs to the source its schema declares, whatever its directory is called, so rename a directory or class (and the imports in its `__init__.py` and `loader.py`) rather than adding a module of aliases.
- Implement each selected loader, then delete its first line, `# biotope:placeholder`. A loader decodes every described field of every row and attaches `Evidence` with the file, a pinned version (such as `sha256:` plus the manifest's checksum) and a row or page location. It does not filter, impute, join or deduplicate: those are selection decisions, and only mappings report them.
- Read files with an established library. Install it where Biotope runs, for example `uv tool install 'biotope[graph]' --with pyshp`, and declare it in `graph/pyproject.toml`: `graph check` warns about an undeclared import, and the build records the installed version of every imported library in `run.json`.
- For a document source, transcribe the reviewed facts into its `Facts` schema; its loader cites each page or section read.

**Step 6: Declare the topology by concept.**

- Write `graph/topology/<concept>/`: one node dataclass and its outgoing relations. Describe every concept in its docstring and every property with `field(metadata={"description": ...})`: what it measures, against which reference, and what it does not establish. Descriptions are the only interpretation that travels with the export; see [interpretation.md](./references/interpretation.md) and [modeling.md](./references/modeling.md).
- **Stop and ask** when two readings of a statistic are both defensible and change which records exist. Present both and the record cost of admitting their union. The default is to admit the union.
- **Stop and ask** before merging identities across sources that do not jointly establish the match. A shared accession establishes it; a matching name, symbol or label does not. The default is separate nodes in source-specific namespaces, such as `symbol:<source>/<symbol>`, so that counting sources never counts one name twice. The rule covers every way records come to compare as one thing: a shared node, or a normalised value such as one common analyte or cell-type label. A match that looks obvious, such as a spelling variant, is still the user's decision. Keep each source's own label, and record the candidate match as an explicit, described link or property, not as the join itself.

**Step 7: Align identities, then write mappings and the pipeline.**

- In `graph/alignment/`, gather identity evidence from every participating source first, then resolve it. Identity comes before admission, an unambiguous resolution must not depend on the order sources were read, and each resolved identity keeps its contributing rows as evidence.

- Write `graph/mappings/<concept>/` and the stage sequence in `graph/pipelines/compose.py`. Mappings select, join and construct. Send every record you do not emit through `context.exclude(...)`, against a policy declared in `Pipeline.policies`. Put aggregate losses into `context.record_audit(...)` counts.

- Audit yourself: every hit below must sit beside an `exclude` call or increment a recorded count.

  ```bash
  rg -n -g '*.py' '\bcontinue\b|^\s*pass$' graph/alignment graph/pipelines graph/mappings
  ```

**Step 8: Check, fix, build.**

1. Run `biotope graph check --json`. Stdout carries exactly one JSON report and every diagnostic goes to stderr, so parse the two streams separately.
1. Fix each error at its source, using the table below. Never suppress a finding with `Any`, blanket ignores or invented metadata.
1. Repeat until the check reports no errors. Resolve each warning, or explain it in the hand-over.
1. Run `biotope graph build`; it replaces `graph/build/` only after a successful run. Then run `biotope graph metagraph --report graph/build/run.json`.

Biotope derives the export schema from the topology: write no project adapter or hand-written export schema. If the agreed scope will not execute, agree a new one rather than sampling silently.

| Finding                                                                      | Meaning                                                                                                                                                                                  | Fix in                    |
| ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| `inventory.absent`, `inventory.mismatch`                                     | The pipeline is not wired to `INVENTORY`, or a selected source differs from it                                                                                                           | Step 4                    |
| `inventory.stale`, `inventory.manifest_not_generated`                        | A source has no package, or a manifest was never generated                                                                                                                               | Step 4                    |
| `inventory.unselected`, `inventory.conflicting_selection`                    | A source is neither selected nor excluded, or both                                                                                                                                       | Step 4                    |
| `inventory.unknown_exclusion`, `inventory.exclusion_reason`                  | An exclusion names no source, or gives no reason                                                                                                                                         | Step 4                    |
| `inventory.placeholder`                                                      | A selected loader is still the placeholder                                                                                                                                               | Step 5                    |
| `inventory.orphan`, `inventory.manifest_missing`                             | A package's source is no longer described: exclude it, then delete the directory                                                                                                         | Step 4                    |
| `inventory.conflict`, `inventory.manifest_invalid`                           | Two packages claim one source, a source has no or a shared `@id`, a package directory is not a Python identifier, a root is contested, or a manifest cannot be read; nothing was written | Step 3                    |
| `source.drift`                                                               | The manifest changed since the schema's revision was reviewed                                                                                                                            | "When a manifest changes" |
| `source.revision_unavailable`, `source.revision_unrecorded`                  | Contract history is missing; run `biotope source generate`                                                                                                                               | Step 4                    |
| `source.unscoped_field`                                                      | A field `@id` is not under its RecordSet; rescope it in the manifest                                                                                                                     | Step 3                    |
| `source.contract`, `source.opaque`, `standardization.*`                      | A schema does not cover its fields, a value type is unknown, or a term binding is invalid                                                                                                | Step 5                    |
| `topology.undescribed`, `topology.undescribed_property`, `topology.examples` | A consumer would see only a label, or a placeholder concept is registered                                                                                                                | Step 6                    |
| `requirements.*`, `intent.*`                                                 | A purpose requirement is neither bound nor deferred, or the intent is missing                                                                                                            | Step 2                    |
| `python.*`, `mapping.contract`                                               | Authored code is wrong                                                                                                                                                                   | Step 7                    |
| `dependencies.undeclared`                                                    | Graph code imports a library that `graph/pyproject.toml` does not declare                                                                                                                | Step 5                    |

**Step 9: Review and hand over.**

Checks establish structure, not scientific correctness: a dropped eligible record passes all of them. Before handing over, make independent reads for the claims the purpose depends on. Read the original source or a published result, never the pipeline's own selection; compare missing and unexpected records by namespaced ID; and name the source of each expectation. Report these reads in the hand-over; they are not committed as code.

```
Build: graph/build/   Sources: <n> selected / <n> excluded
Excluded sources: <name> — <reason>; ...
Excluded records: <policy> <count>; ...
Deferred: <requirement key> — <reason>
Independent reads: <claim> — <source of the expectation> — <agrees | differs: ...>
Open questions: see graph/ASSUMPTIONS.md
```

Then read `graph/build/schema_config.yaml` as the consumer will, with only the graph and `graph/build/`:

```
- [ ] A consumer can tell which study and comparison each concept belongs to
- [ ] Every numeric property states what it measures and against which reference
- [ ] Every identifier states when it may be joined and when it may not
- [ ] run.json's scope and policies state what the selection excluded
```

Anything unticked returns to Step 6 or Step 7. Human scientific review stays manual.

## When a manifest changes

Follow these steps exactly; each schema holds reviewed work.

1. Register the corrected manifest (Step 3), then run `biotope source generate .biotope/datasets/<name>.jsonld --out graph/sources`. It reports each drifted source, records the new revision and rewrites nothing.
1. Run `biotope graph check --json`. Each `source.drift` finding names the source, lists the field changes (`field <id>: dataType "sc:Float" -> "sc:Integer"`), and carries every JSON-pointer difference in its `examples`.
1. For each change, update that source's schema (types, nullability, bindings) and its loader, and any mapping that reads the field.
1. In that schema, set `__source_digest__` to the full revision the finding names.
1. Re-run the check until no `source.drift` remains.

Never delete a schema to regenerate it: that discards the reviewed bindings, and the new schema would still need the same review.

After code changes, rerun Step 8. During requested cleanup, remove generated outputs such as `graph/build/`, and preserve raw data, manifests, `.biotope/contracts/` and authored code. Do not use `biotope rm raw` for test cleanup.

## References

- [example.md](./references/example.md): read before Step 5, for a complete checked project: terms, schemas, loaders for a table and a document, topology, alignment, mappings and the pipeline.
- [curation.md](./references/curation.md): read in Step 3, when correcting, re-baking or registering a manifest, adding a document by hand, or describing a structured file Baker cannot parse.
- [authoring.md](./references/authoring.md): read in Steps 4, 5 and 7, for the file layout, schema bindings, loader and mapping contracts and `RunContext`.
- [interpretation.md](./references/interpretation.md): read in Steps 2, 6 and 9, for selection versus query filter and what each description must state.
- [modeling.md](./references/modeling.md): read in Steps 6 and 7, before a modeling choice that could erase a distinction (qualifiers, absence states, identity).
- [reports.md](./references/reports.md): read in Steps 8 and 9, for what each check establishes and how to read `run.json` and `provenance.json`.
