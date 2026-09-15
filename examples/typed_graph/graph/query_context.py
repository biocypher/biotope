"""What a consumer must know to read this graph correctly, written for that consumer."""

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
                "The source score multiplied by 2.0, applied to every sample. Ratios between "
                "samples are unchanged; absolute values are not source values."
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
                "anatomical site, and the source states no unit or scale, so scores from different "
                "tissues are not known to be comparable."
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
            question="How do transformed scores compare between samples of one tissue?",
            concepts=("example:sample.doubled_score",),
            limitations=(
                "Only the transformed value is stored; divide by 2.0 to recover a source score. "
                "The distribution covers matched samples only, so it is not the source's.",
            ),
        ),
        Capability(
            key="cross-tissue-scores",
            question="Are scores from different tissues on a comparable scale?",
            concepts=("example:sample.doubled_score", "example:sample.tissue"),
            limitations=("The source declares no unit or scale for score.",),
        ),
    ),
    examples=(
        QueryExample(
            capability="samples-per-person",
            language="cypher",
            query=(
                "MATCH (s:ExampleSample)-[:ExampleFromPerson]->(p:ExamplePerson)\n"
                "// one row per person with at least one matched sample\n"
                "RETURN p.name, count(s) AS samples\n"
                "ORDER BY samples DESC"
            ),
            expectation="One row per person with at least one matched sample.",
        ),
    ),
)
