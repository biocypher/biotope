"""What a consumer must know to read this graph correctly, written for that consumer.

Whoever queries this graph receives labels, properties and values, not this
repository. Declare one Capability per question family the graph is built to
answer and back each with a check in checks.py.
"""

from biotope.graph import QueryContext


QUERY_CONTEXT = QueryContext()
