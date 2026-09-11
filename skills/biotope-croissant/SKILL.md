---
name: biotope-croissant
description: Croissant metadata curation and typed Python knowledge-graph construction with Biotope. Source contracts, topology, loaders, mappings, interpretation context, validation checks, BioCypher export.
---

# Biotope graph projects

**The artifact.** A run directory under `graph/build/<run>/`: BioCypher import files, `provenance.jsonl`, `query_context.json`, and `run.json` whose `validation.state` is `passed` or `unverified`. The consumer receives the graph and `query_context.json`. They do not receive this repository or your reasoning, so a graph without its interpretation context is not a deliverable.

**The unit of work.** One **capability**: a question family the graph is claimed to answer, the interpretations needed to read it correctly, one validation check proving it against the source, and one runnable query example. A capability with no check reports `unchecked`.

**Ownership.** The user owns scientific decisions. You own engineering ones. Where two readings are both defensible, neither of you decides: admit both and let the query choose.

Curation, scaffolding and execution are independent. Do the steps the request needs; describing a dataset does not imply building a graph. Database import, querying and new Baker format handlers are separate work.

**Ask, or push back once.** Ask and wait when the answer changes which records exist or which identities merge. Push back once and then defer when it changes only what is claimed. A weakened claim can be repaired in the interpretation context; a record you never admitted is not recoverable by any query.

## Workflow

Copy this checklist and track progress.

```
Biotope graph project:
- [ ] Step 1: Read the purpose, the inputs and the existing project
- [ ] Step 2: Name the capabilities and agree them with the user
- [ ] Step 3: Curate and register the source metadata
- [ ] Step 4: Declare the topology and the interpretation context
- [ ] Step 5: Author loaders, mappings, pipeline and validation checks
- [ ] Step 6: Check, run and read the reports
- [ ] Step 7: Prove every capability, then hand over
```

**Step 1: Read the purpose, the inputs and the existing project.** Run commands from the project root. Read existing purpose files, `biotope map --show`, and `graph/README.md` if a workspace exists — it documents the scaffold you will edit. Reuse existing purpose, metadata and code. Graph checks and builds need `biotope[graph]`; Pyright needs Node.js on PATH or `pyright[nodejs]`. Initialize only if metadata tracking is missing: `biotope init . --no-prompt`. Scaffolding alone needs no initialization. Reconnaissance only — write no project code yet.

**Step 2: Name the capabilities and agree them with the user.** A purpose and its example questions are evidence of intent, not a specification. Derive the adjacent questions: the neighbouring comparison, evidence that would contradict the expected answer, a second defensible reading of the same statistic, the context needed to interpret a result, and the case where a well-founded "no such record" is the answer. For each candidate capability, name the evidence and the distinctions it needs; that list decides what Step 4 must admit. Capture the agreed purpose with `biotope map --purpose "..." --entity "..." --relation "..."`. Propose adjacent capabilities once with what each costs; if declined, record them as out of scope and move on. **Present the capability list and get explicit confirmation before Step 3.**

**Step 3: Curate and register the source metadata.** Run `biotope add <data-path> --json` for new inputs and review its per-file outcomes, warnings and failures; do not scan environments or previous outputs. Inspect declared fields and exact IDs with `biotope map inspect <manifest> --json`, which reads metadata only and gives no value preview. Preserve the requested source scope, including full-directory scans: one record set becomes one source package, so never split a Croissant file to shape the generated layout. Keep unsupported inputs and partial descriptions visible rather than inventing structure to make a mapping work. Register an evidence-backed correction with `biotope source register <file> --name <managed-name> --reason "<evidence and gaps>"`. Metadata-only work ends here.

**Step 4: Declare the topology and the interpretation context.** Write `graph/topology/` and `graph/query_context.py` before any pipeline code: `biotope graph check` never executes `run`, so it validates both against a stub body and is a real gate at this point. Give every concept a class docstring and every property a `field(metadata={"description": ...})`. Declare one `Capability` per agreed capability, and one `Interpretation` per admission rule, statistic definition, identity condition, qualifier and stated uncertainty. **Stop and ask** when two readings of a statistic are both defensible and change which records exist: present both and the record cost of admitting the union, which is the default. **Stop and ask** before merging identities across sources that do not jointly establish the match; the default is separate nodes in source-specific namespaces.

**Step 5: Author loaders, mappings, pipeline and validation checks.** Generate contracts with `biotope source generate .biotope/datasets/<name>.jsonld --out graph/sources`. Resolve identity in a first pass over every participating source, then emit: an unambiguous resolution must not depend on the order sources were read. Send every record you do not emit through `context.exclude(...)` against a declared policy, and put aggregate losses in `record_audit(...)` counts. Then check yourself — every hit below must sit beside an `exclude` call or increment a recorded count:

```bash
grep -rn --include='*.py' -e '\bcontinue\b' -e '^\s*pass$' graph/pipelines graph/mappings
```

Write one `ValidationCheck` per capability in `graph/checks.py`, each deriving its expectation from the source with a plain reader rather than the project loader. List `graph/checks.py` and `graph/query_context.py` in `Pipeline.code_paths`.

**Step 6: Check, run and read the reports.** Run `biotope graph check --json`. Stdout carries exactly one report and every diagnostic goes to stderr; parse the streams separately. Resolve findings rather than suppressing them with `Any`, blanket ignores or invented metadata.

| Finding                                               | Meaning                                                                         | Return to |
| ----------------------------------------------------- | ------------------------------------------------------------------------------- | --------- |
| `context.invalid`                                     | An interpretation or capability points at something the export will not contain | Step 4    |
| `context.undescribed`, `context.undescribed_property` | A consumer would see only the label                                             | Step 4    |
| `context.no_capabilities`                             | Nothing states what the graph answers                                           | Step 2    |
| `context.unvalidated`, `validation.absent`            | Nothing tests what the graph answers                                            | Step 5    |
| `validation.unchecked_capability`                     | One capability is claimed and untested                                          | Step 5    |
| `validation.failed`                                   | The graph contradicts an expectation; export is blocked                         | Step 5    |
| `python.*`, `mapping.contract`, `source.contract`     | Authored or generated code is wrong                                             | Step 5    |

Then build into a new run directory with `biotope graph build --out graph/build/review-1`. Biotope derives the export schema from topology; add no project adapter or hand-written export schema. **If the agreed scope will not execute, agree a new one** rather than sampling silently.

**Step 7: Prove every capability, then hand over.** Run every declared `QueryExample` against the built graph; a sketch is not evidence that a query works. Then report:

```
Build: graph/build/<run>
Validation: <state>   Capabilities: <n> supported / <n> unverified / <n> unchecked

| Capability | State | Validation check | Expectation derived from | Limitation |

Excluded: <policy> <count>; ...
Deferred: <requirement key> — <reason>
Unverified: <capability> — <what could not be established>
Query examples run: <n>/<n>   (you ran these; run.json records only the declarations)
```

Every other field is readable from `run.json`. `supported` there means every
check bound to that capability passed, and nothing more. Finally read `graph/build/<run>/query_context.json` as the consumer will, with the graph and that document and nothing else:

```
- [ ] A consumer can tell which study and comparison each concept belongs to
- [ ] Every numeric property states what it measures and against which reference
- [ ] Every identifier states when it may be joined and when it may not
- [ ] Every capability states what it does not support
```

Anything unticked returns to Step 4. Human scientific review stays manual.

After metadata changes, regenerate affected contracts and repair authored code; after code changes, rerun Step 6. During requested cleanup, remove or archive run directories and generated reports; preserve raw data, curated metadata and authored code. Do not use `biotope rm raw` for test cleanup.

### References

- [interpretation.md](./references/interpretation.md) — steps 2 and 7: what a capability declares, and what counts as proof that it holds.
- [curation.md](./references/curation.md) — step 3: correcting, registering and re-baking a source description without losing curation.
- [modeling.md](./references/modeling.md) — step 4: which distinction a modeling choice is about to erase, and the shape that preserves it.
- [authoring.md](./references/authoring.md) — step 5: what the type checker and the runtime require of loaders, mappings and the pipeline.
- [reports.md](./references/reports.md) — steps 6 and 7: what each check establishes, what it cannot see, and how to read a run.
