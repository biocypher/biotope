# 026 — Strict mapping contracts and typed composition

## 1. Purpose and scope

Make mapping signatures enforce the connections between source records, intermediate
representations and topology objects. Authors should discover incompatible edits during
`biotope graph check`, before loading data.

The current topology constructors provide useful static checks. The gap is in registration
and composition: `Mapping` loses function signatures, `context.apply` returns
`SourceRecord[object]`, and registered output types can disagree with return annotations.

**Scope: Biotope only.** Update the engine, repository examples, scaffold, documentation,
skill and relevant tests.

**The current INTRAC graph (`/Users/vlad/Projects/virtual-human-dev/usecases/intrac`) is
completely out of scope.** It is a transient test project that will be regenerated. Do not
migrate, repair, execute or validate it for this update. Do not copy its implementation into
regression fixtures or preserve compatibility for it. Its regeneration is not a deliverable
or acceptance dependency.

Preserve project-owned Python transformations, useful intermediate records, automatic
contributor propagation and existing graph integrity checks. Compatibility with the old
mapping API is not required.

Also out of scope: a declarative expression language, Paul's compiler/DuckDB machinery,
readers, scientific policies, new graph diagnostics, source-generation changes, unrelated
cleanup and scientific acceptance.

## 2. Public contract

### Mapping signatures are authoritative

```python
def normalise(
    source: SourceRecord[RawRow],
) -> Iterator[Observation]:
    row = source.value
    yield Observation(value=row.measurement)


NORMALISE = Mapping(
    name="project:normalise",
    function=normalise,
    evidence=("Rationale for this transformation.",),
)
```

- `Mapping` preserves the callable's parameter specification and output element type
  (`ParamSpec` + a generic element type, valid on the supported Python versions).
- No constructor arguments for independently authored `inputs`/`outputs`. Runtime contracts
  and report metadata derive from annotations.
- Mapping functions accept one or more explicitly named `SourceRecord[T]` parameters and
  return ordinary dataclass values. Biotope attaches contributor evidence to those outputs.
- Any number of required positional or keyword-only inputs. Variadic parameters, defaults
  and untyped parameters are rejected in registered mappings.
- Concrete dataclass input types, including finite unions. Returns may be parameterized
  `Iterable`, `Iterator`, `Generator`, lists and tuples, including heterogeneous output
  unions and fixed tuples.
- Unresolved annotations, bare containers, `Any`, `object` and unresolved type variables are
  rejected at mapping boundaries. Existing handling of opaque source fields is unchanged.

Helpers inside a project may continue to accept plain values. Only registered mappings
require the evidence-bearing signature.

### Composition retains those types

```python
for observation in context.apply(NORMALISE, source):
    # observation is SourceRecord[Observation]
    context.map(MAKE_GRAPH_OBJECTS, observation, resolved_gene)
```

- `context.apply` checks arguments against the mapping's signature and returns precisely
  typed `SourceRecord` objects.
- `context.map` provides the same argument checks and accepts only graph-object outputs,
  via a small structural protocol based on the existing `schema_id` declaration; topology
  classes need no new inheritance.
- Actual membership in the selected topology remains a definition/runtime check.
- Heterogeneous registration exposes a read-only, non-executable interface. Concrete mapping
  objects are imported for invocation; a registry entry provides no unchecked dispatch route.
- Public `context.emit(value, ..., mapping="name")` is retired. Collection is internal to
  checked mapping execution. Project aggregations produce typed intermediate records and pass
  them through registered mappings.

Scaffold guidance demonstrates buffering typed intermediate records, not untyped
mapping/record pairs recovered with casts.

## 3. Validation and runtime behaviour

One contract-resolution implementation serves definition checks and runtime enforcement.
Annotations resolve once per mapping within a check/run, not per record.

`graph check` must:

- Validate mapping signatures without invoking mappings or loaders.
- Verify that output classes declaring graph identity belong to the selected topology.
- Collect independent mapping errors with mapping identity, function location and the
  offending parameter or return annotation.
- Preserve structured Pyright diagnostics, existing human/JSON conventions and explicit
  blocked-stage reporting.
- Keep derived input/output information in reports, sourced from the function signature.

During execution:

- Validate evidence and input values before calling the mapping.
- Forward the original `SourceRecord` arguments without unwrapping them.
- Validate every yielded value against the derived output contracts.
- Attach the combined evidence of all input records, preserving contributor semantics.
- Retain identifier, duplicate/conflict, topology-membership and endpoint checks.
- Preserve single execution per quality/build operation and existing failure reports.

These guarantees apply to the supported public API. Deliberate casts, ignored diagnostics and
private API access are not globally prohibited.

## 4. Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Signature preservation | `Mapping(Generic[P, E])` with `function: Callable[P, Iterable[E]]` | `ParamSpec` is available on 3.10+; verified to preserve positional, keyword-only and heterogeneous-tuple element types under strict Pyright. |
| Composition signatures | `apply(mapping: Mapping[P, E], *args: P.args, **kwargs: P.kwargs) -> Iterator[SourceRecord[E]]` | Argument checking and precise output typing in one construct. |
| Graph-output restriction | `map(mapping: Mapping[P, G], ...)` with `G` bound to a `GraphObject` protocol declaring `schema_id: ClassVar[str]` | Structural; topology dataclasses need no inheritance. Unions of graph objects satisfy the bound. |
| Read-only registry | `MappingEntry` `Protocol` exposing only `name`, `requirements`, `evidence` | Non-constructible and offers no `function` attribute, so `Pipeline.mappings` cannot dispatch. |
| Contract resolution | New `biotope/graph/signatures.py` with a cached `contract(entry)` | Single implementation for check and runtime; one reflection pass per mapping. |
| Collection | `RunContext._collect` (private), reached only through `map` | Removes the public unchecked emission route. |

Feasibility was verified with pyright 1.1.411 at `--pythonversion 3.10` before implementation:
`SourceRecord[Observation]` and `Sample | Person | FromPerson` are inferred without casts, and
wrong record types, unwrapped values, missing/extra arguments, invalid keywords, swapped
inputs, an intermediate mapping passed to `map`, and `entry.function` access are all errors.

## 5. Acceptance criteria

Meaningful regression tests were defined **before implementing each behaviour**, using the real
strict Pyright checker. Repository-owned synthetic fixtures only.

| ID | Required evidence | State |
|---|---|---|
| **A1 — Signature enforcement** | Wrong record types, swapped inputs, missing/extra arguments and invalid keyword arguments fail static checking at the composition call. | complete |
| **A2 — Type preservation** | Two different source normalizers produce a shared intermediate type, followed by a multi-input graph mapping. Intermediate and heterogeneous graph output types stay precise without author-side casts or `object` recovery. | complete |
| **A3 — Topology protection** | Incorrect constructor fields, property types and endpoint identifier types fail checking. Passing an intermediate-producing mapping to `context.map` fails static checking. Unregistered graph output classes fail definition checking. | complete |
| **A4 — One contract** | No separately authored input/output registration remains. Supported return shapes produce correct derived contracts; invalid signatures are reported together without executing project data code. | complete |
| **A5 — No unchecked public route** | Registry entries cannot be used for untyped invocation. Public direct emission is removed, and all repository consumers use the checked path. | complete |
| **A6 — Runtime protection** | Deliberately misbehaving functions still fail on invalid values or undeclared outputs. Multi-input and multi-stage evidence propagation, deduplication, conflicts and endpoint validation retain protection. | complete |
| **A7 — Workflow stability** | Existing synthetic graph contents and provenance remain correct. Quality/build execute once; failures remain parseable and incomplete measurements remain marked as not run. | complete |
| **A8 — Delivered authoring experience** | Packaged scaffold and repository examples pass strict checks without payload files. Documentation and skill consistently teach the new API and explain normalization versus graph construction. | complete |

Existing graph fixtures and integration tests were reused. One compact composition fixture
(`tests/graph/composition/`) and grouped negative cases cover the distinct guarantees. No
exhaustive parameter matrices, trivial helper tests, duplicate export runs or real-data tests.

## 6. Delivery checklist

1. **Establish the contract** — failing static composition tests; public API locked.
   - [x] `tests/graph/composition/` fixture and `tests/graph/test_contracts.py`
   - [x] `Mapping`/`MappingEntry`/`GraphObject` public shape
2. **Implement registration and execution.**
   - [x] `biotope/graph/signatures.py` contract resolution, cached per registration
   - [x] `RunContext.apply`/`map` typed composition; `emit` retired to `_collect`
   - [x] runtime evidence, dedup, conflict and endpoint behaviour retained
3. **Integrate definition checking.**
   - [x] `check.py` mapping stage uses the shared contracts
   - [x] topology membership of graph outputs checked at definition time
   - [x] report `inputs`/`outputs`/`concepts` derived from signatures
4. **Update authoring materials.**
   - [x] `examples/typed_graph` migrated (normalizer + graph mapping)
   - [x] `biotope/templates/graph` scaffold migrated, incl. buffered intermediates
   - [x] `docs/mapping.md`, skill reference and `SKILL.md`, scaffold README, `templates/AGENTS.md`
   - [x] short API migration example in `docs/mapping.md`
5. **Verify and review.**
   - [x] every acceptance ID has recorded evidence
   - [x] public signatures inspected for type erasure
   - [x] obsolete code/tests removed

## 7. Current next step

Complete. A1, A6 and A8 were reopened by review on 2026-09-10 and re-closed with the
additional evidence recorded in the review-resolution log entry below.

## 8. Blockers

None.

## 9. Implementation log

### 2026-09-10 — feasibility probe

Ran a scratchpad prototype through pyright 1.1.411 at `--pythonversion 3.10`.
`Mapping(Generic[P, E])` + `apply(mapping, *args: P.args, **kwargs: P.kwargs)` preserves
`SourceRecord[Observation]`; a `-> tuple[Sample, Person, FromPerson]` mapping infers
`Sample | Person | FromPerson` and satisfies a `GraphObject`-bounded type variable.
A `MappingEntry` protocol without `function` rejects `REGISTRY[0].function(row)`.
Ten negative composition cases all produced errors. No blocker; proceeding as designed.

### 2026-09-10 — contract established (step 1)

`biotope/graph/contracts.py` exports `GraphObject`, `MappingEntry` and `Mapping(Generic[P, E])`;
the `inputs`/`outputs` constructor arguments are gone. `tests/graph/composition/` holds the
compact fixture — two normalizers sharing `Measurement`, then a two-input heterogeneous graph
mapping — with `precise.py` (positive precision assertions) and `invalid.py` (20 grouped
negative cases, each carrying the diagnostic substring it must produce). `test_contracts.py`
runs the real strict checker at `pythonVersion 3.10` over both and requires an error on every
marked line and on no other line.

### 2026-09-10 — registration, execution and definition checking (steps 2-3)

`biotope/graph/signatures.py` derives one `MappingContract` per registration, cached by the
registration value, and serves both `check.py` and `RunContext`. `apply`/`map` bind arguments
through the resolved signature, validate evidence and input values, forward the original
`SourceRecord` objects and validate every yielded output. `RunContext.emit` became
`_collect`, reachable only through `map`. `check.py`'s mapping stage reports each parameter or
return problem independently with the mapping identity and the authored function's
file and line, refuses graph outputs missing from the topology, and keeps derived
`inputs`/`outputs`/`concepts` in the report (`metagraph` overlays still resolve).

One design note: `MappingContract` stores no callable. The concrete `Mapping[P, E]` is the only
thing ever invoked, so the internal `_authored()` read exists purely for reflection and nothing
in the engine can dispatch through an erased function type.

### 2026-09-10 — authoring materials (step 4)

`examples/typed_graph` now normalizes (`Measurement` intermediate) before constructing graph
objects, and the pipeline streams samples through both steps. The scaffold's
`mappings/_example.py` shows the same split and `pipelines/_example.py` buffers a
`list[SourceRecord[ExampleValue]]`, with a comment on why an untyped mapping/record buffer
would check nothing. `docs/mapping.md` gained the signature-first description, the supported
annotation rules and a before/after migration example; the skill reference, `SKILL.md`, the
scaffold README and `templates/AGENTS.md` teach normalization versus graph construction.

### 2026-09-10 — verification (step 5)

Evidence per acceptance ID:

- **A1/A3 (static)** — `test_contracts.py::test_incompatible_composition_fails_static_checking`
  drives pyright over `composition/invalid.py`; all 20 grouped cases produce their expected
  diagnostic and nothing else errors.
- **A2** — `::test_composition_keeps_intermediate_and_graph_types` (zero errors over the
  fixture and `precise.py`, which annotates `SourceRecord[Measurement]` and
  `Sample | Donor | TakenFrom` without casts), plus the `erased`/`collapsed` negative cases
  that rule out an `Any` satisfying both.
- **A4** — `test_check_mappings.py::test_supported_shapes_derive_their_contract` (10 return and
  parameter shapes) and `::test_invalid_signatures_are_reported_together_without_running_project_code`
  (14 registrations reported independently with file/line; the pipeline's `run` never executes).
- **A5** — `MAPPINGS[0].function(...)` and `context.emit(...)` are static errors;
  `grep -rn "\.emit(" --include="*.py" --include="*.md" biotope tests examples docs skills`
  returns only that negative case.
- **A6** — `test_runtime.py` covers misbehaving functions (bad property value, unnamespaced
  identifier, undeclared output class), unwrapped arguments, missing arguments, unregistered
  mappings, dedup, conflicts and endpoint validation;
  `test_contracts.py::test_multi_stage_execution_combines_evidence_and_deduplicates` covers
  source → intermediate → graph evidence propagation across two normalizers.
- **A7** — `test_example.py` (real checker, real BioCypher build, graph digest equality across
  runs, provenance evidence counts, failure reports) and `test_quality.py` (single execution,
  `not_run` measurements on failure) pass unchanged in intent.
- **A8** — `test_scaffold.py` strictly checks the packaged scaffold with no payload files;
  `test_example.py` deletes `raw/` and still passes `graph check`.

Commands run:

- `pytest -q` → 196 passed (30 in `tests/graph`), on Python 3.12 and Python 3.10.
- `pyright` (strict, repository config) → 0 errors, on Python 3.12 and Python 3.10.
- `ruff check --select=E,F,I .` and `ruff format --check` → clean for every touched file.

Unrelated pre-existing issue, left alone: `ruff check --select=I` reports `I001` on the
generated `biotope/_version.py`.

### 2026-09-10 — review resolution (A1, A6, A8 reopened and re-closed)

Three findings from adversarial review, all confirmed by reproduction before fixing.

**1. Combined evidence hid an input with none (A6).** `_bind` validated the union of all
inputs' contributors, so a two-input graph mapping accepted a donor record with empty
evidence and emitted the donor node carrying only the assay's provenance. `_bind` now
validates each input's contributors as it binds it, before any value validation and before
the mapping function runs, and `_evidence` takes an optional subject so the message names
the offending parameter. Reproduced and confirmed fixed:
`fixture:build-objects input 'donor': Every graph/source record needs source evidence …`
with no node emitted. Regression:
`test_runtime.py::test_every_input_needs_its_own_evidence` — one valid plus one
empty-evidence input fails with the function never entered, a blank-location contributor is
also rejected, and valid multi-input provenance still combines to two contributors.

**2. Framework parameter names collided with forwarded keywords (A1).** A legitimate
signature such as `def transform(*, mapping: SourceRecord[Row])` resolved fine but
`context.apply(MAPPING, mapping=row)` raised "got multiple values for argument mapping".
`apply` and `map` now take `self` and `mapping` positional-only (`/`), so those names belong
to the mapping's signature rather than to the helper. Reproduced and confirmed fixed for a
mapping with keyword-only inputs named both `mapping` and `self`. Regressions:
`test_runtime.py::test_mappings_may_use_the_composition_helpers_own_parameter_names`
(execution through `apply` and `map`) and `composition/precise.py`
`reserved_input_names_do_not_collide`, which the real strict checker must accept.

**3. Guidance made the intermediate mandatory (A8).** The skill, skill reference,
`docs/mapping.md`, scaffold README and `templates/AGENTS.md` instructed a normalization
mapping and intermediate dataclass for every graph. All five now state that mapping a source
row straight to topology objects is the normal shape, and that an intermediate earns its place
when several sources converge on one shape, when a stage needs buffering or aggregation, or
when one normalization feeds several graph mappings. The two-step scaffold and worked
examples remain — the scaffold must still demonstrate buffering typed intermediates — but
each now says in its docstring that it is shown as the form worth writing down, and how to
collapse it to a single mapping.

Re-verified after the fixes: `pytest -q` → 198 passed, and strict `pyright` → 0 errors, both
on Python 3.12 and Python 3.10. Ruff `E,F,I` and format are clean for every touched file
(`biotope/_version.py`, `biotope/metadata.py` and `biotope/commands/mv.py` carry pre-existing
findings and were not touched).
