# Review: typed graph engine and the graph scaffold

## 1. The runbook dead-ends on the Daria workbook step

Runbook section 2 instructs `biotope add context/darias_input.xlsx`. Reproduced with a real
workbook:

```
SKIP   darias_input.xlsx
       No handler
Total  1 scanned · 0 described · 1 not described
Saved  .biotope/datasets/context/darias_input.jsonld (0 record sets)
Next   biotope map inspect .biotope/datasets/context/darias_input.jsonld
```

The command saves an empty manifest and then
points Vlad at an inspection that shows nothing. The CLI output is honest, and the route
forward exists — author a description and `source register` it — but the runbook does not
connect that route to this step. Its caveat in that section covers Zarr, not xlsx.

Say the workbook is expected to skip with "No handler", and point at the `source register`
route documented six lines below. Every other runbook command and flag exists and behaves as
written; I checked all eight commands and all six flags.

## 2. The spec cites two evidence documents that do not exist

Neither file is in `.planning/data-harmonization-and-paper/`:

- `02-typed-graph-engine.review-resolution.md`, cited at spec lines 217 and 290. It is the
  only evidence for the "Review follow-up" section and the whole `F1`–`F15` disposition.
- `02-typed-graph-engine.real-data-check.md`, cited at lines 262 and 291. It is the only
  evidence for the Daria, INTRAC and Open Targets results: 30 manifests, 29 files, 1,632
  Parquet files and the three selected builds.

The fixes and the real-data work are real — I verified the fixes myself — but a reader
cannot confirm either from the record. Restore both files or remove the claims that depend
on them.

Two smaller inconsistencies in the same document. "Readiness evidence" states "174 tests in
12.00 seconds" while the implementation log states 172 passed with four Baker failures; I
measured 172 passed and 4 failed in 23.1 s. And `02-typed-graph-engine_sidenotes.md:115`
links `01-croissant-baker-update.runbook.md`, which moved to `old/`.

## 3. The scaffold and the example teach different layouts, and only one is tested

`biotope graph scaffold` produces a registry layout: `SOURCES`, `TOPOLOGY` and `MAPPINGS`
tuples in the three `__init__.py` files, imported by `pipelines/build_graph.py`, with
package-relative imports and no `__init__.py` in the topology concept directories.

`examples/typed_graph/` uses an inline layout: all four `__init__.py` files empty, no
registries, `SourceContract` and `Topology` constructed inline in `build_graph.py`, absolute
`graph.` imports, and `__init__.py` present in the topology directories.

The agent is pointed at both. `graph/README.md:36` mandates the registries and is the file
the skill and the runbook tell the agent to read first. `docs/mapping.md` and
`docs/tutorial.md` never mention the registries, point at the example as the executable
reference, and `docs/tutorial.md:29` presents the two as interchangeable.

`tests/graph/test_example.py::prepare` scaffolds the template and then copies the example
over it with `dirs_exist_ok=True`, overwriting the three registry modules with the example's
empty files. B3, B5, B6 and B7 are therefore all verified against a hybrid project in which
`sources/_example/__init__.py` uses registration style beside an empty
`sources/people/__init__.py`. No test covers the layout the README prescribes. I confirmed
that layout works: with the registries filled and the template's own `build_graph.py` kept,
`biotope graph check` passes, including strict Pyright.

This is a documentation and coverage defect, not a code defect. Keep the registry
convention, which puts the mechanical wiring in a fixed place the agent fills, then convert
the example to it, stop the test from overwriting the registry modules, name the convention
in `docs/mapping.md` and the skill reference, and add the two missing
`topology/_example_*/__init__.py` files so template and example agree.

## 4. `source generate` leaves the per-source wiring to the agent

```console
$ biotope source generate .biotope/datasets/raw.jsonld --out graph/sources/raw/schema.py
Generated: graph/sources/raw/schema.py
$ ls -A graph/sources/raw/
schema.py
```

No `__init__.py`, no loader stub and no `SourceContract`. The generated module also exposes
no record inventory, so `SourceContract(records=(...))` is filled by reading the file and
transcribing class names. For Open Targets, the named next dataset, that is 55 names by
hand, repeated after any regeneration that adds a record set. `check_pipeline` verifies that
each listed record is generated and fresh, but not that the list is complete, so an omission
is silent.

This is mechanical work the model assigns to the CLI. Three additions close it:

1. emit `RECORDS: tuple[type, ...]` in the generated module;
1. write a sibling `__init__.py` with the `SourceContract` filled in, unless one exists —
   the refuse-rather-than-overwrite rule `generate_source` already applies to authored code;
1. write a loader stub beside it when absent, so implementing one function is the agent's
   only remaining task for a new source.

## 5. `graph check` reports clean in two cases where it should warn

**Unstated purpose.** On a fresh project, `intent` carries an empty purpose and empty
required lists, so `required` and `missing` are both empty and the check succeeds with
`warnings: []`. Nothing distinguishes a satisfied purpose from a purpose that was never
stated. The same happens when `find_project()` finds nothing: coverage is skipped silently.
The runbook captures this JSON into `.biotope/reviews/definitions.json`, and it is the
signal a reviewer focused on competency questions will look at.

**Placeholder concepts.** Filling in only `name` and `scope` — the two mechanical fields —
and registering the template's own `_example` topology gives a clean pass with
`topology: ['example:collection', 'example:in-collection', 'example:record']`. `graph build`
is still blocked by the unimplemented loader and `build()`, so this cannot reach a graph
today, but it will once the agent implements a loader and forgets to replace the topology.

Three warnings cover both: no required entities or relations declared, no intent found, and
a registered concept ID in the `example:` namespace.

## 6. `register --replace` drops curated content without reporting it

Running the recovery route exactly as `protect_curated` and the runbook instruct, the
annotation edit disappeared with no warning:

```console
$ biotope source register reviews/fresh.jsonld --name raw --reason "reconciled: kept citation" --replace
Registered curated metadata: .../.biotope/datasets/raw.jsonld
# citation:  None   (was 'Reviewed citation 2026')
# curation:  {'reason': 'reconciled: kept citation'}
```

`register_metadata` never compares the incoming description with the one it replaces, and
`--reason` is unverified free text — mine claimed the opposite of what happened. The
`annotation_review` note that recorded the edit goes too.

Reconciliation is correctly the human's job, and the spec rules out a merge editor. But this
route implements B1's "rebaking preserves edits or stops before overwriting them", and its
last step currently has no guard. Report which top-level keys and record-set or field IDs
exist in the manifest being replaced but not in the incoming one. Vlad will use this route
on Daria and INTRAC during B9.

## Deferred

These are real but not worth time now. Details in [the sidenotes](spec2_review2_sidenotes.md).

- **Runtime performance.** `emit` runs at 55–60k objects/s; a 200-field record validates at
  5,600 rows/s, and sparse records cost roughly twice as much as populated ones because
  union dispatch uses a caught exception per null field. Cheap fixes exist. The spec excludes
  full-corpus processing, so this matters only when Open Targets scale is actually in front
  of you.
- **`test_example.py` structure.** One 90-line test with 12 CLI invocations carries B3, B5,
  B6 and B7, so a failure does not say which criterion broke. Worth splitting during B9
  defect triage, not before.
- **Housekeeping.** Inconsistent `Evidence` serialization, an undocumented
  `dataclasses.Field` mutation, unchecked working-directory assumptions, two retirement
  crumbs and four small diagnostic or efficiency items.

## Spec and scope

Spec adherence is strong. Every required deliverable is present. Every excluded item is
absent: no expression DSL, query compiler, scheduler, reader framework, `kg-build-system`
dependency, Jinja, or second YAML authority. The responsibility table holds — no format
reader exists in `biotope/` or its templates, the loader stub raises, and the only `csv`
import is in the example project. Definition checks work with payloads absent; the example
test deletes `raw/` entirely. One type checker, as directed.

For the paper, the mechanical/intelligent split is the instrument, not just ergonomics. Arm
B's advantage should come from the agent spending its intelligence on scientific decisions
rather than plumbing, so items 3 and 4 are paper findings: every hand-assembled
`__init__.py`, every transcribed record tuple and every minute spent choosing between two
documented layouts is scaffolding cost inside the measured `B − A`. Item 5 is the one a
reviewer will ask about directly.

The machinery stayed small, and this review pass shrank it further rather than expanding it,
which matches Sebastian's position that it is a minor detail rather than the main message.
Both fixes should stay in that category.
