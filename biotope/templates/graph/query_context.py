"""What a consumer must know to read this graph correctly, written for that consumer.

Whoever queries this graph receives labels, properties and values. They do not
receive this repository, the build log or the reasoning behind any decision, so
every rule needed to filter, join, compare a direction or decline an
unsupported conclusion has to be declared here and shipped with the export.

Declare a capability for each question family the graph is built to answer and
back each one with a check in ``checks.py``. An undeclared capability claims
nothing; a declared one with no check is reported as untested::

    from biotope.graph import Capability, Interpretation, QueryContext, QueryExample

    QUERY_CONTEXT = QueryContext(
        interpretations=(
            Interpretation(
                subject="<concept ID>.<property>",
                # selection | statistic | identity | qualifier | uncertainty
                kind="statistic",
                statement="What this measures, against which reference, and what it does not establish.",
                # Another reading already present in this graph; a reading that
                # needs a rebuild is a capability limitation, not an alternative.
                alternatives=("<concept ID>.<other property>",),
            ),
        ),
        capabilities=(
            Capability(
                key="<short-key>",
                question="The question family this graph is claimed to answer.",
                concepts=("<concept ID>",),
                limitations=("What a reader must not conclude from it.",),
            ),
        ),
        examples=(
            QueryExample(
                capability="<short-key>",
                language="cypher",
                query="MATCH ... RETURN ...",
                expectation="What a correct run returns.",
            ),
        ),
    )
"""

from biotope.graph import QueryContext


QUERY_CONTEXT = QueryContext()
