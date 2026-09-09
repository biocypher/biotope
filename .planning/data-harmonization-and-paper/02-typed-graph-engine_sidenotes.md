# Typed graph engine — examples and evidence

Supporting material for [spec 2](02-typed-graph-engine.spec.md). Examples illustrate responsibility boundaries; names and signatures are not a fixed API. The specification defines required behavior.

## Project layout

```text
.biotope/datasets/
  study_a.jsonld                # Effective curated source description

graph/
  sources/
    __init__.py                # SOURCES registry
    study_a/
      __init__.py              # SOURCE, initially created by source generate
      schema.py                # Generated records and inventory
      loader.py                # Authored access/decoding; starts as a stub
  topology/
    __init__.py                # TOPOLOGY registry
    sample/
      __init__.py
      node.py
      from_patient.py
    patient/
      __init__.py
      node.py
  mappings/
    __init__.py                # MAPPINGS registry
    study_a.py                 # Authored transformations
  pipelines/
    build_graph.py             # Imports registries; explicit composition
```

Source classes follow metadata; topology follows graph concepts. Outgoing edges live beside their source node. Stable schema identifiers establish graph identity independently of import paths. Generated files are replaceable; authored loaders, mappings, topology, and pipelines are preserved.

## Declarations and mappings

This example assumes the source contract permits a missing tissue value. It omits surrounding registration, validation, and provenance envelopes to keep the data types visible.

```python
from dataclasses import dataclass, field
from typing import ClassVar, NewType


# Generated from curated Croissant metadata.
@dataclass(frozen=True)
class SampleRow:
    sample_id: str = field(
        metadata={"croissant_id": "study-a/samples/sample_id"}
    )
    patient_id: str
    tissue: str | None


# Authored topology and identity types.
SampleId = NewType("SampleId", str)
PatientId = NewType("PatientId", str)


@dataclass(frozen=True, kw_only=True)
class Sample:
    schema_id: ClassVar[str] = "study:sample"
    id: SampleId
    tissue: str | None


@dataclass(frozen=True, kw_only=True)
class SampleFromPatient:
    schema_id: ClassVar[str] = "study:sample-from-patient"
    source: SampleId
    target: PatientId


# Project mapping. This example scopes identifiers to study A.
def map_sample(row: SampleRow) -> Sample:
    return Sample(
        id=SampleId(f"study-a:sample:{row.sample_id}"),
        tissue=row.tissue,
    )


def map_patient_relation(row: SampleRow) -> SampleFromPatient:
    return SampleFromPatient(
        source=SampleId(f"study-a:sample:{row.sample_id}"),
        target=PatientId(f"study-a:patient:{row.patient_id}"),
    )
```

A complete project also defines and emits patients. Runtime validation checks that relation endpoints resolve. A `NewType` conversion does not prove a raw identifier is valid; that assertion belongs to the identity policy. In a real project, use a shared explicit policy rather than scattering identifier prefixes across mappings.

The signatures below illustrate the execution boundary. Placeholder types are conceptual; the loader uses a format library, and mappings receive its typed results. Source envelopes carry evidence references.

```python
def load_samples(source: StudyASource) -> Iterator[SourceRecord[SampleRow]]:
    ...


def combine_samples_and_outcomes(
    samples: Iterable[SourceRecord[SampleRow]],
    outcomes: Iterable[SourceRecord[OutcomeRow]],
) -> Iterable[SourceRecord[SampleWithOutcome]]:
    ...
```

The writer separately derives BioCypher configuration from topology and translates graph objects to tuples. Provenance can remain in a linked sidecar rather than adding technical properties to each domain class.

## Generation and validation considerations

Croissant carries source extraction, references, semantic types, and structural descriptions as well as row fields. Keep that metadata in Croissant; generated types retain only compact references to its fields. Known scalars and nested records can be generated mechanically; unknown semantic types and arbitrary matrix layouts need explicit representation policies.

Pydantic is already a dependency in the inspected Biotope baseline. It can validate configurations and source contracts, including dataclasses. Choose coercion deliberately: accepting a converted value differs from proving the original value matched its declaration. Make intended source decoding explicit and use strict validation where appropriate.

- [Croissant 1.1 specification](https://docs.mlcommons.org/croissant/docs/croissant-spec-1.1.html).
- [Python dataclass typing](https://typing.python.org/en/latest/spec/dataclasses.html), [NewType](https://typing.python.org/en/latest/spec/aliases.html#newtype), and [protocols](https://typing.python.org/en/latest/spec/protocol.html).
- [Pydantic dataclasses](https://pydantic.dev/docs/validation/latest/concepts/dataclasses/) and [strict mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/).

## Manual test context

The existing [spec 1 runbook](old/01-croissant-baker-update.runbook.md) uses:

- Daria project: `/Users/vlad/Projects/virtual-human-dev/daria_mvp/data`.
- INTRAC project: `/Users/vlad/Projects/virtual-human-dev/biotope-bench/data/intrac_260731/workspace`.
- Opentargets data: /Users/vlad/Projects/virtual-human-dev/usecases/opentarget/opentargets-25.12 . It has an `output` for raw data and a manually written `meta/croissant.json` that we can use for comparison, but not as a golden standard (it's not perfect)
- Local Biotope and baker installed together in each project's environment, currently using Python 3.12.
- Metadata for the full `raw` directory, plus Daria's `context/darias_input.xlsx`, followed by spot checks and Claude Code review.

Part 2 keeps that source-review scope and adds typed authoring and selected graph execution. Reuse completed scans. Source descriptions do not oblige a graph to ingest every measurement. Zarr has no required baker handler or loader; evidence-based manual metadata is allowed. Document new commands and agent prompts once implemented.

The spec 1 cleanup procedure archives the whole `mappings` directory. Part 2 must distinguish authored mappings/loaders/topology and curated corrections from generated outputs before offering reset commands.

## Inspected baseline and design influence

Earlier exploration inspected Biotope `0.8.0` at `9465817` and Paul's clean `kg-build-system` checkout at `22fedcd`, version `0.1.0`. These are historical source-inspection anchors, not the spec 1 handoff or evidence of current runtime compatibility. Recheck the working tree during implementation.

Biotope already generates typed source-field descriptors. Its older engine uses YAML/Pydantic mappings, generated BioCypher adapters, and custom acquisition code. Spec 2 replaces the relevant authoring/execution architecture after spec 1's removals.

Paul's package demonstrates independent topology, typed source fields, expression-based bindings, immutable compilation artifacts, and configurable execution modules. It distinguishes property templates, abstract categories and concrete components; its category hierarchy is a restricted tree. The chosen Biotope design uses ordinary typed Python mappings and project-owned execution. His expression language, relational planner, readers, hierarchy and universal compiler/executor interface are not adoption requirements.

His component symbols include module/class names, and his hierarchy notes say an earlier negative static-checker demonstration was removed. Those findings motivate stable semantic identifiers and a few real checker demonstrations; they do not justify an exhaustive testing framework or assess future maintenance quality.

His component-scoped keys, scalar graph properties, native CSV/JSON/Parquet inputs and Neo4j output differ from Biotope's existing CURIE/string identities, alignment conventions and BioCypher integration. Those differences inform the new explicit identity and export contracts; they do not create compatibility requirements. The inspected repository used blueprint schema 4 while an earlier unified specification described 3, reinforcing the need to verify executable behavior rather than treat its plans as an integration contract. The pre-spec's dependency, authority and migration questions are resolved by the final spec; they are not open decisions.

## Final review and spec 1 handoff

Reviewed the spec, code and runbook on 8 September 2026. At initial review, the integration branch and the detached authoring worktree shared `9465817` but had different uncommitted changes. Before this document handoff, spec 1 was committed on `feat/dataset_harmonization` at `2242c62`, including the Daria mapping feedback fixes. That commit is the implementation base. Full-directory/INTRAC review and the published-baker release gate remain pending. The findings below describe the review snapshot; refresh them when implementation begins.

| Area                 | Observed handoff / review finding                                                                                                                                                             | Resulting instruction                                                                                                                                |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Engine transition    | [CLI](../../biotope/cli.py) no longer registers build. The old build module still imports removed API functionality.                                                                          | Treat old construction as detached code; do not reattach it wholesale or repair all legacy graph commands.                                           |
| Source contracts     | The [Croissant model](../../biotope/croissant/spec.py) and [inspector](../../biotope/croissant/inspector.py) retain richer descriptions, but display summaries are not full source contracts. | Generate types from Croissant and retain field references; keep descriptive metadata in the authoritative manifest.                                  |
| Curated metadata     | [Ingestion](../../biotope/commands/add.py) rewrites manifests; [skill guidance](../../skills/biotope-croissant/SKILL.md) prohibits managed-file editing and stops before value loading.       | Add a supported authoring/preservation route and update the workflow; do not assume existing annotations preserve arbitrary structural corrections.  |
| Retained behavior    | Spec 1 keeps purpose, metadata and YAML mapping tools; spec 2 makes Python authoritative.                                                                                                     | Preserve purpose/metadata outcomes and replace affected authoring/checking paths without maintaining a second engine.                                |
| Dataset evidence     | Spec 1 records Daria subset feedback; its corrections are now committed. Full-directory review and INTRAC agent acceptance remain incomplete.                                                 | Reuse actual evidence and coordinate inherited blockers; runbook instructions alone do not prove coverage.                                           |
| Completion and scope | The earlier checklist allowed outstanding in-scope defects and lacked evidence/status fields.                                                                                                 | B1–B8 define readiness; B9 defines manual acceptance. Required failures block their criteria. Bounded examples and manual checks remain the default. |
| Long implementation  | The earlier checkpoint omitted ownership, revisions and decisions; delegation had no contract.                                                                                                | Keep one resume record and concise log; delegate independent slices with explicit ownership and proportionate verification.                          |

The review also bounded unknown-type handling, joins, provenance storage, fingerprinting, metadata preservation and obsolete-code cleanup. Their required outcomes remain; universal engines, extra backend implementations and broad audits are excluded. No application tests or dataset scans were run for this document review.

### Local source references

- Current implementation: [dependencies](../../pyproject.toml), [source generation](../../biotope/graph/sources.py), [contracts](../../biotope/graph/contracts.py), [topology](../../biotope/graph/topology.py) and [output](../../biotope/graph/output.py). The baseline YAML generator and adapter templates were retired.
- [Baker format limitations](/Users/vlad/Projects/virtual-human-dev/croissant-baker/docs/user-guide/supported-formats.md), including workbook and HDF5 descriptions without executable extraction instructions.
- [Paul's package metadata](/Users/vlad/Projects/kg-build-system/pyproject.toml), [license](/Users/vlad/Projects/kg-build-system/LICENSE), [topology](/Users/vlad/Projects/kg-build-system/kg_build_system/topology/models.py), [binding factories](/Users/vlad/Projects/kg-build-system/kg_build_system/binding/factories.py), [compiler symbols](/Users/vlad/Projects/kg-build-system/kg_build_system/compile/compiler.py).
- [Reference build](/Users/vlad/Projects/kg-build-system/reference_project/build.py), [module interface](/Users/vlad/Projects/kg-build-system/kg_build_system/modules/interfaces.py), [type fixtures](/Users/vlad/Projects/kg-build-system/tests/typecheck_graph_bindings.py), [hierarchy limitations](/Users/vlad/Projects/kg-build-system/NODE_EDGE_HIERARCHY_SPEC.md).
- [Source trust and nullability](/Users/vlad/Projects/kg-build-system/SOURCE_SCHEMA_TRUST_AND_NULLABILITY_SPEC.md), legacy Biotope alignment semantics (retired; see baseline commit `2c3676a`).
