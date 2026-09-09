# Sidenotes: second review of the typed graph engine

Supporting detail for [the review](spec2_review2.md). Nothing here needs action before B9.

## First-review fixes, as reproduced

Each entry was rerun rather than read from the disposition record.

| ID    | Result                                                                                                                                                                                                                                                                                   |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `F1`  | Fixed. 55 × 200 fields (11,000 fields, 4.66 MB module) is strict-Pyright clean in 1.0 s with 0 errors. Descriptors moved from attribute defaults into one `json.loads` blob. Open Targets is 4,003 fields. Import cost 0.37 s, `get_type_hints` 0.06 s.                                  |
| `F2`  | Fixed end to end. The lock is written only when `annotate apply` changes metadata. Full cycle confirmed: edit, lock, `add --rebake` refused, `add --bake-to`, `source register --replace`, unblocked. Item 6 of the review covers what the last step still loses.                        |
| `F3`  | Fixed. `source_definition()` narrows the digest to `@context` and `recordSet`, so checksums and review notes no longer force regeneration.                                                                                                                                               |
| `F4`  | Fixed in `check.py:115`. 8.67 s to 0.06 s over a 55 × 200 manifest. The same pattern survives in `topology.py:54`; see below.                                                                                                                                                            |
| `F5`  | Fixed. The `needs_unknown` flag replaced text-based import pruning, so a field description containing "UnknownValue" can no longer produce an unused import.                                                                                                                             |
| `F6`  | Fixed. `ConceptExampleSampleHa03435e4ed` became `ExampleSample`. The hash suffix now applies only to a genuine normalization collision or the writer's synthetic `Entity` root, with a post-check and a regression test.                                                                 |
| `F7`  | Addressed. The BioCypher 0.9.7 asymmetry — scalars unescaped in `_write_node_data`, list items escaped via `_write_array_string` — is named in a comment, the version is pinned with a reason, and `test_output.py` round-trips both paths including a rejected literal array separator. |
| `F9`  | Fixed. `_software()` records the version, the `direct_url.json` editable flag, VCS info when present, and a `source_digest` over every `biotope/**/*.py`, so an uncommitted working tree stays identifiable. The example test asserts digest stability across runs.                      |
| `F10` | Fixed. `write_text_atomic` uses a private temporary directory so new files honor the umask, and preserves the existing mode on replacement.                                                                                                                                              |
| `F11` | Fixed. `croissant/api.py` and all of `croissant/acquisition/*.py` are gone. The queue's `MAPPED` bucket is reachable through `mark --status mapped` and its label says so.                                                                                                               |
| `F14` | Fixed. `ExclusionFinding` aggregates a count with a ten-item evidence sample and a truncation flag. Measured at 537k calls/s; the membership scan I flagged in the first review is not a hot spot.                                                                                       |

`F8`, `F12`, `F13` and `F15` were retained by decision, consistent with the spec.
Mapping-call evidence grain is documented in three places, requirement IDs are deferred to
part 3, and `deepcopy` on emit is retained.

Other claims checked:

- **Test baseline.** 172 passed and 4 failed in 23.1 s. The four Baker format failures
  reproduce at base commit `2c3676a` with base code on the path, so the deferral is correct.
  The local baker ships no Excel or HDF5 handler module: `handlers/` contains csv, tsv, json,
  parquet, image, dicom, fhir, nifti, wfdb and soft.
- **Packaging.** The wheel carries all 19 template files, including the two topology
  directories without `__init__.py`, carries `py.typed`, and contains no trace of the old
  engine.
- **Strict Pyright** on `biotope/graph` plus the two CLI modules: 0 errors, 0 warnings.

## Runtime performance

Measured on this machine, Python 3.12.13. The spec excludes full-corpus processing and
documents in-memory execution, so none of this blocks acceptance. These are the numbers to
know before Open Targets.

`RunContext.emit` runs at 55–60k objects/s. `cProfile` attributes it to `validate_value`
(51%) and `deepcopy` (34%).

- `deepcopy(value)` costs 3.3 µs per object and protects nothing for a frozen dataclass of
  scalars, which is what every topology concept in the example and template is. Only
  `list[str]` properties can be mutated by a caller after emit.
- Three lookups are recomputed on every emit: the `next(...)` scan over `pipeline.mappings`,
  `cls not in (*topology.nodes, *topology.edges)` which allocates a new tuple each call
  before scanning it, and a second scan for `cls in topology.edges`. All three are fixed
  sets known at `__init__`.

Precomputing those three and skipping the copy for all-scalar concepts measured 1.34× on
emit in a prototype.

`validate_value` scales linearly with record width:

| Record width | Populated     | 90% null     | 1.6M rows, populated then sparse |
| ------------ | ------------- | ------------ | -------------------------------- |
| 8 fields     | 145,000 rec/s | 85,000 rec/s | 0.2 min, 0.3 min                 |
| 50 fields    | 24,700 rec/s  | 13,800 rec/s | 1.1 min, 1.9 min                 |
| 200 fields   | 5,600 rec/s   | 3,000 rec/s  | 4.8 min, 8.8 min                 |

Sparse records are the slow case and sparse is the default case. A `str | None` annotation
tries `str` first and uses a raised-and-caught `ValueError` for union dispatch, so every
null field costs one exception. Generated fields default to nullable and real biological
tables are sparse. Dispatching `None` before trying members measured 1.36× at 50% null and
about 2.1× at all-null, with every diagnostic string preserved.

Caveat on that number: my harness showed real run-to-run variance, with the fully-populated
baseline swinging between 75k and 119k rec/s across runs, and I measured no reliable gain on
fully-populated records. The null-heavy improvement was consistent and has a clear
mechanism.

### The same `F4` pattern in a hotter place

`topology.py:54` calls `hints(expected)` once per field, inside the per-field loop:

```python
validate_value(getattr(value, member.name), hints(expected)[member.name], f"{location}.{member.name}")
```

`hints` is `lru_cache`d, so this is a cache lookup rather than a resolution, but hoisting it
above the loop is a one-line change with no behavior difference. Two related costs on the
same path: the per-field `f"{location}.{member.name}"` is built for every field of every
record, measured at about 9% of `validate_value`; and `load()`, `apply()` and `emit()` each
build a location string containing the `repr` of the evidence tuple before knowing whether
anything failed, at about 0.9 µs per record. Making those diagnostics lazy is a larger
change and not worth it now.

### Peak memory at the end of a run

`build.py` materializes a full `asdict` copy of every node and edge to compute
`graph_digest`, then JSON-serializes it, so peak memory is roughly three times the graph.
This is consistent with the documented in-memory design. Worth one line in `variability` or
the docs so it is not a surprise at scale.

## Test structure

`tests/graph/test_example.py` is one test function with 12 CLI subprocess invocations, each
running Pyright: 8.6 s of the 12.7 s `tests/graph` runtime. It carries B3, B5, B6 and B7
through interleaved mutations of mapping text, raw CSV and the manifest, and includes
unexplained magic numbers such as `assert len(first["findings"]) == 2`.

Total volume is right — 10 functions across 747 lines is proportionate, and the spec asks
for that restraint. Serialization is a separate choice from volume. An assertion failure at
the renamed-property stage blinds every later stage, and a red test does not say which
criterion broke. Splitting into about four tests over a module-scoped fixture localizes
failures and allows a subset to be rerun during defect triage, at no extra runtime.

`tests/graph/test_output.py` and `test_scaffold.py` are well-targeted. The scaffold test's
symlink and byte-for-byte preservation assertions are exactly right.

## Housekeeping

- **Two serializations of `Evidence`.** `runtime.py:163` uses `e.__dict__` and
  `output.py:185` uses `asdict(e)`. Beyond the inconsistency, `__dict__` blocks adding
  `slots=True` to `Evidence` later, which is the natural memory win for a design that
  retains all evidence in memory. Use `asdict` in both.
- **`source_metadata` mutates a `dataclasses.Field` after construction.**
  `member.metadata = MappingProxyType(...)` is what made the `F1` fix possible and it works,
  but `Field.metadata` is not a documented mutation point; CPython happens to leave the slot
  writable. The docstring explains why the indirection exists and should also name that
  assumption, so a future maintainer knows what a Python upgrade could break and that
  `test_sources.py` is the canary.
- **Working directory is load-bearing and unchecked.** `_pipeline()` inserts it into
  `sys.path`, `check_types` passes it as Pyright's `extraPaths`, and `find_project()` walks
  up from it. Running `graph check` from the wrong directory gives only
  `Error: No module named 'graph'`. A hint naming the project root would remove a class of
  confused report. Separately, `graph scaffold` succeeds in a directory that is not a
  Biotope project and writes a README instructing commands that need `.biotope/`; compare
  `source register`, which says "Run biotope init first".
- **Stale-record diagnostic.** `check_pipeline` interpolates the raw object, so a bad
  `records=` tuple yields `rows: stale or non-generated record 2`. Name what was passed.
- **Small waste.** `code_files(pipeline)` walks the tree twice per check, once in
  `check_pipeline` and once in `check_types`. The reserved-`preferred_id` check in
  `output.py` runs per row rather than per concept.
- **Readability.** `properties()` in `output.py` uses `for val in (getattr(value, key),)` as
  a let-binding. Correct, but obscure enough to warrant a plain loop or a helper.
- **Generated module namespace.** The generated module exposes `json`, `dataclass`,
  `ClassVar` and `annotations` as public names while aliasing only `source_metadata` to
  `_source_metadata`. Underscore-alias them all.
- **Retirement crumbs.** `tests/integration/test_metadata_workflow.py:37` still guards
  against importing `biotope.croissant.acquisition.context`, a module that no longer exists,
  so the entry is a no-op in an otherwise valuable negative-import test.
  `biotope/croissant/acquisition/` survives as an empty directory holding only
  `__pycache__`.

## The checker ceiling, for future reference

The `F1` fix moved the Pyright ceiling rather than removing it, and the failure mode is now
diagnosed. At 90k fields the module reaches 38 MB and Pyright emits one "Code is too complex
to analyze" plus one "Untyped class decorator obscures type of class" per record set. The
decorator errors are a consequence of the complexity bailout, not independent problems, and
they disappear entirely at 11k fields. `check.py` catches the signature and gives the right
instruction. Recorded so that a future reader seeing 300 decorator errors reads the first
line and splits the contract instead of chasing the decorator.

## Carried forward for the paper pilot

Two measurement points from the first review that still hold. Arm B fails closed where arm A
degrades gracefully: a stale contract, an opaque field or an unbound requirement stops the
build. And the scaffolding-to-first-graph cost is a distinct quantity from the authoring
cost, so it is worth instrumenting separately rather than absorbing into `B − A`.
