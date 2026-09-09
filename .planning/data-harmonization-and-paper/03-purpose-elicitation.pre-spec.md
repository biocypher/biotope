# Pre-spec 3 — Purpose elicitation, shared understanding, and evaluation

Status: initial exploration, 8 September 2026. This provides context for later clarification and design. The paper draft is a source of hypotheses and experiment ideas, not an approved protocol or established result.

## Goal

Make researcher–agent agreement on scientific purpose a central, revisable part of Biotope: what the researcher wants to learn or decide, which questions the work must support, which assumptions matter, and what would count as a useful and adequately supported result. Preserve that understanding through construction, new data, changed questions, and corrections, so the interaction can later be evaluated.

The aim is useful shared understanding, not a longer fixed questionnaire or requiring researchers to design graph schemas before describing their needs.

## Initial findings

- **The interview is mainly instructions.** Skill/template questions cover purpose, entities, relations, and available/missing datasets. `init` and the mapping wizard capture free text and flat lists; there is no interview-state model.
- **Persistence is minimal.** `Project` stores name, purpose, entity/relation/source lists, and notes. It lacks structured questions, acceptance criteria, evidence limits, unresolved choices, and decision history. Unknown YAML fields are ignored and can disappear on rewrite, so prose instructions alone cannot establish a durable expanded record.
- **Construction checks declared names.** Scaffolding creates slots; purpose appears as a comment. Discovery ranks entity overlap. Build checks resolution and name coverage, not scientific answerability.
- **Evaluation concerns graph integrity.** Counts, orphaned edges, compile drops, and ID consistency exist; benchmark coverage/alignment metrics remain placeholders. Tests cover persistence and mapping/build mechanics, not elicitation quality or research-task acceptance.
- **Authority and revision are inconsistent.** Git versions intent without explaining decisions. The template forbids unrequested entity/relation changes while the skill allows additions. Deferred required relations can still fail project-wide coverage. These tensions need resolution.

The consulting brief supplies choices beyond entity lists: metadata/raw-data access, field usefulness, uncertainty, rejected-study reasons, and reviewer effort. The paper draft adds observation-unit distinctions and revisions such as tissue location versus patient outcome. These motivate questions; underlying data and biological interpretations were not validated here.

## Provisional direction

Explore a compact, versioned **purpose record** with an adaptive interview around it. Possible contents are:

| Area                     | What shared understanding should capture                                                                  |
| ------------------------ | --------------------------------------------------------------------------------------------------------- |
| Research use             | The decision/comparison, intended user, deliverable, and boundaries of the task                           |
| Questions                | Concrete questions and examples of useful answers; priorities and dependencies                            |
| Scientific scope         | Population, tissue, observation unit, source scope, inclusion/comparison/aggregation rules where relevant |
| Evidence and uncertainty | Supporting sources, known limitations, disagreements, assumptions, and choices awaiting the researcher    |
| Acceptance               | Observable checks, review criteria, critical errors, and what would justify an evidence-limited answer    |
| Revision                 | What changed, who settled it, why, and which questions, mappings, or checks are affected                  |

These are candidate areas, not mandatory fields. Separate inspectable facts from researcher decisions. Ask in dependency order, use small source examples, stop when the task is actionable, and reopen relevant choices after new evidence or needs. Define those rules during detailed design.

Keep scientific requirements distinguishable from topology and bindings. The [typed-engine work](02-typed-graph-engine.spec.md) can check implementation contracts; the purpose record explains why a contract is appropriate. The [format work](/Users/vlad/Projects/virtual-human-dev/biotope/.planning/data-harmonization-and-paper/01-croissant-baker-update.spec.md) supplies evidence about available fields and extraction limits. A missing field should trigger an explicit limitation or a research decision, not an unrecorded change in purpose.

## Foundation for later experiments

The draft's ordinary-agent/Biotope comparison tests the whole workflow; replaying elicited records into an identical builder could help isolate elicitation. Preserve records, source references, revisions, and role-specific effort information to enable such experiments. The full experiment ladder and sample counts remain tentative.

Keep researcher-visible construction questions separate from hidden evaluation answers. Candidate outcomes are deliverable correctness/usefulness, justified evidence limitations, researcher/specialist effort, and successful revisions without regressions. Question count, agreement, and graph validity alone do not establish value.

## Handoff from the typed engine

Part 2 currently binds requirements by `entity:<exact intent text>` and
`relation:<exact intent text>`. Rewording a requirement requires updating the
binding; checks report the mismatch. Give requirements stable IDs in the purpose
record and adapt these bindings there, keeping one requirement-reference scheme.

## Questions for the detailed specification

- Does elicitation cover research tasks that may justify tables or other outputs, or must every episode target a graph?
- Which parts of the purpose record are required, task-dependent, or deliberately free text?
- Can the first implementation be a skill plus a persisted record and CLI support, or is a dedicated interview controller needed?
- What establishes sufficient agreement to proceed, and which scientific or implementation changes require renewed agreement?
- How should unsupported/deferred questions remain visible while useful partial work proceeds?
- Which acceptance checks belong in Biotope, and which independent evaluation and effort instrumentation belong in `biotope-bench`?
- Which small consulting and paper cases should pilot the protocol before its wording, schema, and evaluation are frozen?

## Source anchors

- [Current orientation and build loop](/Users/vlad/Projects/virtual-human-dev/biotope/skills/biotope-croissant/SKILL.md:30), [generated orientation questions](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/templates/AGENTS.md:55), [intent model](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/project_model.py:25).
- [Mapping wizard](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/commands/map_wizard.py:957), [build's intent inputs](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/commands/build.py:111), [coverage checks](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/croissant/scaffold/materialize.py:411).
- [Benchmark implementation](/Users/vlad/Projects/virtual-human-dev/biotope/biotope/commands/benchmark.py:46), [intent synchronization tests](/Users/vlad/Projects/virtual-human-dev/biotope/tests/unit/test_wizard_intent_sync.py).
- [Consulting brief](/Users/vlad/Projects/virtual-human-dev/biotope/.planning/data-harmonization-and-paper/data-harmonizaton.md), [tentative paper and evaluation plan](/Users/vlad/Projects/virtual-human-dev/biotope/.planning/data-harmonization-and-paper/biotope_paper1_purpose_and_expertise.md).
