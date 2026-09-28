# Interpretation that travels with the graph

The consumer receives the graph and `graph/build/`: labels, properties,
`biotope_provenance_id`, the descriptions in `schema_config.yaml`, and the scope,
policies and settings in `run.json`. Everything they need to read a value
correctly must be in one of those places.

## Separate selection from query filters

A selection rule determines which records exist in the graph. A query filter
operates on those retained records. If two intended readings require different
populations, discuss admitting their union: a second property on the retained
subset cannot recover rows excluded during construction.

State a selection rule twice. The pipeline's `policies` name each exclusion a
mapping reports through `context.exclude(...)`, with the rule a reviewer can
check; the `scope` states the selected inputs and output grain. A threshold kept
as a property lets a consumer tighten it in a query; one applied during
construction cannot be loosened without a rebuild, and the policy must say so.

## What each description must state

Descriptions are authored where the concept or property is declared, in the class
docstring and `field(metadata={"description": ...})`. Each kind of rule has a
home:

| Rule        | State                                                               | Where                                      |
| ----------- | ------------------------------------------------------------------- | ------------------------------------------ |
| Selection   | Which records were admitted and by what rule                        | `Pipeline.policies`, `scope`, the concept  |
| Statistic   | What the value measures, its reference and its calculation          | The property description                   |
| Identity    | When identifiers can be joined and where identity is unresolved     | The identifier's concept and the relation  |
| Qualifier   | Cohort, timepoint, treatment or other context needed for comparison | A queryable property, described            |
| Uncertainty | What the value or evidence does not establish                       | The property description; `ASSUMPTIONS.md` |

For a property retained under a strict adjustment, this states both the
statistic and the selection it implies:

```python
strict_p: float = field(
    metadata={
        "description": (
            "Benjamini-Hochberg adjusted p over the authors' filtered gene set, as reported. "
            "Rows with strict_p >= 0.05 were not admitted (policy above_admission_band)."
        )
    }
)
```

A reading that needs excluded records is a limitation: say so in the concept or
property description and in the policy, not only in the hand-over.

## Keep open questions visible

A scientific interpretation the sources do not settle — an unrecorded contrast
orientation, a cohort overlap, an identity the evidence does not establish — goes
into `graph/ASSUMPTIONS.md` with what would resolve it, and into the hand-over.
Keep the affected description honest about it.

## Review with independent reads

Builds check structure, not scientific correctness. Before relying on a claim,
read the original source, a published result or a curated answer to establish
the expectation. Never derive it from the pipeline's own selection: reusing the
code that built the graph reproduces its mistakes. Compare both missing and
unexpected records, using consistent namespaced IDs, and name the source of each
expectation. Report these reads in the hand-over; they are review work, not
committed code.

Review the export alongside the graph to ensure statistics, selection rules,
identities and limits are understandable without access to the development
conversation.
