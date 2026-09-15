# Capabilities and interpretation

## Define a question family

`Capability(key, question, concepts, limitations)` states what a graph is intended
to answer. Its concepts identify the relevant topology; its limitations describe
questions the selected population cannot support.

`supported` in `run.json` means every bound validation check passed. It does not
establish that every interpretation is sufficient or that a query example ran.
A capability with no check reports `unchecked`; a check returning `unknown` leaves
its capability `unverified`.

Before fixing scope, consider adjacent comparisons, contradictory evidence,
alternative readings, necessary context and meaningful absence results. Expand
only where relevant to the agreed purpose and feasible resources.

## Separate selection from query filters

A selection rule determines which records exist in the graph. A query filter
operates on those retained records. If two intended interpretations require
different populations, discuss admitting their union. A second property on the
retained subset cannot recover rows excluded during construction.

`Interpretation(subject, kind, statement, alternatives)` binds a rule to a concept
ID or `<concept ID>.<property>`.

| Kind          | State                                                                |
| ------------- | -------------------------------------------------------------------- |
| `selection`   | Which records were admitted and by what rule                         |
| `statistic`   | What the value measures, its reference and calculation               |
| `identity`    | When identifiers can be joined and where that identity is unresolved |
| `qualifier`   | Cohort, timepoint, treatment or other context needed for comparison  |
| `uncertainty` | What the value or evidence does not establish                        |

For a topology with `study:measurement.strict_p`, this declaration describes a
bounded selection:

```python
from biotope.graph import Capability, Interpretation, QueryContext

QUERY_CONTEXT = QueryContext(
    interpretations=(
        Interpretation(
            subject="study:measurement.strict_p",
            kind="selection",
            statement="Only rows with strict_p < 0.05 were retained.",
        ),
    ),
    capabilities=(
        Capability(
            key="retained-significance",
            question="Which supplied measurements passed the strict adjustment?",
            concepts=("study:measurement",),
            limitations=("Rows failing the strict adjustment are absent.",),
        ),
    ),
)
```

`alternatives` must refer to concepts or properties in the actual topology. A
reading requiring excluded records belongs in the capability's limitations.
Add `QueryExample` declarations using actual export labels and runnable queries;
report separately whether they have been executed.

## Derive independent expectations

`ValidationCheck(name, function, capability, evidence)` runs after reference
integrity and before export. Its function takes `(GraphView, tuple[Audit, ...])`
and returns a `ValidationResult`.

Read the original source, a published result or a curated answer to establish the
expectation. Reusing the pipeline's selection code can reproduce its mistakes.
Compare both missing and unexpected records, using consistent namespaced IDs.
Name the expectation's source in `evidence`.

- `ValidationResult.ok(...)` records a pass.
- `ValidationResult.wrong(...)` fails validation and blocks export.
- `ValidationResult.unknown(...)` records an unresolved question as `unverified`.

A check that raises fails the run. State the missing evidence when returning
`unknown`, including which capability it affects.

## Review the exported context

`query_context.json` and the exported `BiotopeQueryContext` rows carry the
interpretations to graph consumers. Review them alongside the graph to ensure
statistics, selection rules, identities and limits are understandable without
access to the development conversation.
