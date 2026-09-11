"""What a consumer must know to read this graph correctly, written for that consumer.

The person querying this graph gets labels, properties and values. They do not
get the build log, this repository or the reasoning behind any decision, so
every rule they need in order to filter, join or compare has to be declared
here and shipped with the export.
"""

from biotope.graph import Capability, Interpretation, QueryContext, QueryExample


QUERY_CONTEXT = QueryContext(
    interpretations=(
        Interpretation(
            subject="example:sample",
            kind="selection",
            statement=(
                "Only samples whose person_id matches a row in people.csv are present. "
                "Counting samples here counts matched samples, not the source's samples."
            ),
        ),
        Interpretation(
            subject="example:sample.doubled_score",
            kind="statistic",
            statement=(
                "score x 2.0, applied to every sample by the same fixed multiplier. "
                "Ratios between samples are unchanged; absolute values are not source values."
            ),
        ),
        Interpretation(
            subject="example:person.id",
            kind="identity",
            statement=(
                "Minted from this study's person_id under the 'fixture' scope. Join on it within "
                "this graph only; it carries no meaning in any other dataset."
            ),
        ),
        Interpretation(
            subject="example:sample.tissue",
            kind="uncertainty",
            statement=(
                "A free-text source label, lowercased. Equal strings are not evidence of the same "
                "anatomical site, and different strings are not evidence of different ones."
            ),
        ),
    ),
    capabilities=(
        Capability(
            key="samples-per-person",
            question="Which samples belong to a given person, and how many does each person have?",
            concepts=("example:sample", "example:person", "example:from-person"),
            limitations=("Counts cover matched samples only; unmatched samples are absent entirely.",),
        ),
        Capability(
            key="score-comparison",
            question="How do transformed scores compare between samples or between people?",
            concepts=("example:sample.doubled_score",),
            limitations=(
                "Only the transformed value is stored. A question about raw score magnitude "
                "needs a rebuild, not a different query.",
            ),
        ),
    ),
    examples=(
        QueryExample(
            capability="samples-per-person",
            language="cypher",
            query=(
                "MATCH (s:ExampleSample)-[:ExampleFromPerson]->(p:ExamplePerson) "
                "RETURN p.name, count(s) AS samples ORDER BY samples DESC"
            ),
            expectation="One row per person with at least one matched sample.",
        ),
    ),
)
