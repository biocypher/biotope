# Capabilities and their proof

## A capability is a question family, not a concept list

`Capability(key, question, concepts, limitations)` states a question someone will actually ask. Naming the concepts it touches is not the same claim: a graph can hold every concept a question mentions and still lack the row that answers it.

`supported` in `run.json` means one thing and only one thing: every validation check bound to that capability returned a pass. It is not a claim that the interpretations are sufficient, that the expectation was truly independent, or that any query was ever run — the package cannot see those. A capability with no check reports `unchecked`; a capability whose check returned `unknown` reports `unverified`.

So declare the rest and check the rest yourself: the interpretations a reader applies, and a `QueryExample` you have executed against the built graph. Running the examples is a step you perform and report; nothing in `run.json` records that it happened.

## Name the adjacent questions before you fix scope

A purpose arrives with a few example questions. Those are a sample of intent. Work outward from them before deciding what to load:

- the neighbouring comparison, in the same study or a sibling one
- evidence that would contradict the expected answer
- a second defensible reading of the same statistic
- the context a result needs to be interpretable — cohort, reference group, unit
- the question whose correct answer is "no such record"

Widen selection where that materially improves usefulness. Do not expand into unrelated research, and do not fall back on loading everything. Reduce on relevance or on a measured resource limit you can name.

## Inclusion is not a query default

Separate the rule that admits a record from the filter a query applies. When two interpretations are both plausible and they change which records exist, admit the union: a property stored beside rows that were never admitted does not make the other reading available, and declaring it as an alternative is then false.

## Each interpretation kind answers one question

`Interpretation(subject, kind, statement, alternatives)` binds a rule to a concept ID or `<concept ID>.<property>`.

| Kind          | Must state                                                     | Without it, a consumer will                             |
| ------------- | -------------------------------------------------------------- | ------------------------------------------------------- |
| `selection`   | Which records were admitted, and on what test                  | count a filtered subset as the whole                    |
| `statistic`   | What the value measures, against which reference, how computed | compare two numbers that mean different things          |
| `identity`    | When two identifiers may be joined, and when not               | join across a boundary the sources never established    |
| `qualifier`   | The context that changes what the claim means                  | pool results from different cohorts, timepoints or arms |
| `uncertainty` | What the value does not establish                              | rank or compare on an orientation nobody recovered      |

```python
QUERY_CONTEXT = QueryContext(
    interpretations=(
        Interpretation(
            subject="study:measurement.strict_p",
            kind="selection",
            statement="Rows were admitted on strict_p < 0.05, which excludes low-count features.",
            alternatives=("study:measurement.open_p",),
        ),
    ),
    capabilities=(
        Capability(
            key="significance",
            question="Which measurements are significant under either adjustment?",
            concepts=("study:measurement",),
            limitations=("Only rows passing the strict adjustment were admitted.",),
        ),
    ),
    examples=(QueryExample(capability="significance", language="cypher", query="MATCH ..."),),
)
```

## An alternative names a property in this graph

`alternatives` is resolved against the real topology by `biotope graph check`. A reading that would need a rebuild is a `Capability.limitation`, not an alternative. The same pass reports capabilities nothing tests, and concepts or properties with no description.

## Derive the expectation outside the pipeline

`ValidationCheck(name, function, capability, evidence)` runs after reference integrity and before export. Its function takes `(GraphView, tuple[Audit, ...])` and returns a `ValidationResult`.

```python
def eligible_rows_present(view: GraphView, audits: tuple[Audit, ...]) -> ValidationResult:
    """Compare the graph with an expectation read straight from the source."""
    expected = {row["id"] for row in read_source_table() if eligible(row)}
    found = {m.id for m in view.records(Measurement)}
    if found != expected:
        return ValidationResult.wrong(f"Missing {sorted(expected - found)}", missing=len(expected - found))
    return ValidationResult.ok(f"All {len(expected)} eligible rows are present.")
```

Read the source with a plain reader. A check that calls the project loader agrees with the pipeline by construction, and is blind to exactly the records it exists to find. Name the source of the expectation in `evidence`: a source table, a published figure, or a curated answer.

## `unverified` records missing knowledge, and is not a pass

`ValidationResult.ok`, `.wrong` and `.unknown` are the three outcomes. `.unknown` reports state `"unverified"` — the constructor and the reported state use different words. `.wrong` blocks the export. `.unknown` leaves its capability unresolved and every other capability usable. A check that raises is recorded as failed.

Prefer `.unknown` with a named gap over silence. State what could not be established and which capability it costs.

## The interpretation context is the entire handoff

`query_context.json` and the `BiotopeQueryContext` rows in the export are what the consumer receives. A rule in a decision document, a commit message or a conversation does not reach the agent querying the database. Before handing over, read the document with the graph and nothing else and confirm each statistic, admission rule, identity condition and stated limit is recoverable from it alone.
